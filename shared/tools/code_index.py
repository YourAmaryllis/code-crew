"""
CodeIndexTool — semantic search over the current workspace using ChromaDB.

Chunks source files into overlapping line windows, embeds them with a
sentence-transformer model (runs fully locally, no API key required), and
stores them in a persistent ChromaDB collection under .code-crew/code-index/.

Two operations:
  index   — build or rebuild the index for the current workspace
  search  — semantic similarity search; returns top-N chunks with file:line refs

Embedding model is configurable via CODE_INDEX_EMBEDDING_MODEL (or the
semantic_search.embedding_model config key). Default is all-MiniLM-L6-v2,
which uses ChromaDB's bundled ONNX runtime — no extra pip installs needed.
Other models require sentence-transformers: pip install sentence-transformers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_CHUNK_LINES = 50
_OVERLAP_LINES = 10
_NOISE_DIRS = {
    ".git", "vendor", "node_modules", "__pycache__", ".terraform",
    ".code-crew", "dist", "build", ".venv", "venv", ".mypy_cache",
}
_CODE_EXTS = {
    ".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt",
    ".rb", ".rs", ".cs", ".cpp", ".c", ".h", ".tf", ".sh", ".bash", ".sql",
}
_MAX_INDEX_FILES = 2000
_COLLECTION_NAME = "workspace"


def _index_dir() -> Path:
    """Resolve the ChromaDB persistence directory for the current workspace."""
    override = os.environ.get("CODE_INDEX_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.cwd() / ".code-crew" / "code-index"


def _model_name() -> str:
    return os.environ.get("CODE_INDEX_EMBEDDING_MODEL", _DEFAULT_MODEL).strip()


def _make_embedding_function(model: str):
    """Return a ChromaDB embedding function for the given model name."""
    if model == _DEFAULT_MODEL:
        # Uses chromadb's bundled onnxruntime — no extra deps needed.
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        return DefaultEmbeddingFunction()
    # Other models require: pip install sentence-transformers
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=model)
    except ImportError:
        raise RuntimeError(
            f"Model '{model}' requires sentence-transformers: "
            "pip install sentence-transformers"
        )


def _get_collection(index_path: Path, model: str):
    """Return (client, collection) for the workspace index."""
    import chromadb
    index_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_path))
    ef = _make_embedding_function(model)
    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def _iter_chunks(root: Path):
    """Yield (doc_id, text, metadata) for all indexable source files under root."""
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= _MAX_INDEX_FILES:
            break
        if not path.is_file():
            continue
        if any(part in _NOISE_DIRS for part in path.parts):
            continue
        if path.suffix not in _CODE_EXTS:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        rel = str(path.relative_to(root))
        step = _CHUNK_LINES - _OVERLAP_LINES
        start = 0
        while start < len(lines):
            end = min(start + _CHUNK_LINES, len(lines))
            chunk_lines = lines[start:end]
            text = "\n".join(chunk_lines)
            if text.strip():
                doc_id = f"{rel}:{start + 1}"
                yield doc_id, text, {"file": rel, "start_line": start + 1, "end_line": end}
            start += step
        count += 1


class CodeIndexInput(BaseModel):
    operation: str = Field(
        description=(
            "Operation to perform. One of:\n"
            "  index   — build or rebuild the semantic index for the current workspace\n"
            "  search  — find code by meaning (e.g. 'authentication middleware', "
            "'database connection pooling', 'error handling for HTTP timeouts')"
        )
    )
    query: str = Field(
        default="",
        description="Search query (natural language). Required for the search operation.",
    )
    n_results: int = Field(
        default=5,
        description="Number of results to return (search operation only, default 5, max 20).",
    )


class CodeIndexTool(BaseTool):
    name: str = "code_index"
    description: str = (
        "Semantic search over the current project's source code using local embeddings.\n"
        "Use 'search' to find code by meaning — e.g. 'JWT validation', 'database retry logic', "
        "'all HTTP handler functions'. Returns file:line references and relevant code chunks.\n"
        "Use 'index' to build or rebuild the search index (done automatically by /explore)."
    )
    args_schema: type[BaseModel] = CodeIndexInput

    def _run(self, operation: str, query: str = "", n_results: int = 5) -> str:
        if operation == "index":
            return self._build_index()
        if operation == "search":
            return self._search(query, n_results)
        return f"Unknown operation '{operation}'. Use: index, search."

    def _build_index(self) -> str:
        root = Path.cwd()
        index_path = _index_dir()
        model = _model_name()

        try:
            import chromadb
        except ImportError:
            return "ERROR: chromadb not installed — pip install chromadb"

        try:
            client, collection = _get_collection(index_path, model)
        except Exception as exc:
            return f"ERROR: failed to open ChromaDB collection: {exc}"

        # Delete existing docs so we do a clean rebuild.
        try:
            existing = collection.count()
            if existing:
                all_ids = collection.get(include=[])["ids"]
                if all_ids:
                    collection.delete(ids=all_ids)
        except Exception:
            pass

        ids, docs, metas = [], [], []
        for doc_id, text, meta in _iter_chunks(root):
            ids.append(doc_id)
            docs.append(text)
            metas.append(meta)

        if not ids:
            return f"No indexable source files found under {root}."

        # Upsert in batches of 200 to avoid memory spikes.
        batch = 200
        for i in range(0, len(ids), batch):
            collection.upsert(
                ids=ids[i:i + batch],
                documents=docs[i:i + batch],
                metadatas=metas[i:i + batch],
            )

        files_indexed = len({m["file"] for m in metas})
        return (
            f"Index built: {len(ids)} chunks from {files_indexed} files "
            f"(model: {model}, path: {index_path})"
        )

    def _search(self, query: str, n_results: int) -> str:
        if not query:
            return "ERROR: query is required for search."
        n_results = min(max(n_results, 1), 20)

        index_path = _index_dir()
        if not index_path.exists():
            return (
                "Code index not built yet. Run the 'index' operation first, "
                "or run /explore to build it automatically."
            )

        model = _model_name()
        try:
            _, collection = _get_collection(index_path, model)
        except Exception as exc:
            return f"ERROR: failed to open index: {exc}"

        if collection.count() == 0:
            return "Index is empty — run 'index' operation or /explore to populate it."

        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            return f"ERROR: search failed: {exc}"

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return f"No results for '{query}'."

        sections: list[str] = []
        for doc, meta, dist in zip(docs, metas, distances):
            score = round(1 - dist, 3)  # cosine distance → similarity
            header = f"=== {meta['file']}:{meta['start_line']} (score {score}) ==="
            sections.append(f"{header}\n{doc}")

        return "\n\n".join(sections)


def build_index(root: Path | None = None) -> str:
    """Build the code index for the given root (or cwd). Returns a status string."""
    if root:
        original = Path.cwd()
        import os as _os
        _os.chdir(root)
        try:
            return CodeIndexTool()._build_index()
        finally:
            _os.chdir(original)
    return CodeIndexTool()._build_index()
