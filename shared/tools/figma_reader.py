"""
FigmaReaderTool — fetch frames, design tokens, and rendered images from the Figma REST API.

Requires FIGMA_TOKEN env var (Figma personal access token:
Settings → Account → Personal access tokens).

Supported operations:
  get_frame   — return the component tree for a frame/node as JSON
  get_tokens  — return file design styles (colours, typography, spacing) as a token map
  get_image   — return the rendered PNG URL for a frame
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _figma_get(path: str) -> dict:
    token = os.environ.get("FIGMA_TOKEN", "")
    if not token:
        raise RuntimeError(
            "FIGMA_TOKEN is not set. "
            "Add it to ~/.code-crew/config.yaml under figma.token."
        )
    url = f"https://api.figma.com{path}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Figma API {exc.code}: {body}") from exc


def _parse_figma_url(url: str) -> tuple[str, str]:
    """Return (file_key, node_id) from a Figma URL. node_id may be empty."""
    # https://www.figma.com/file/<KEY>/... or /design/<KEY>/...
    m = re.search(r"figma\.com/(?:file|design)/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Cannot parse Figma file key from URL: {url}")
    file_key = m.group(1)
    # node-id may be URL-encoded (1234%3A5678) or dash-separated (1234-5678)
    qs = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(qs)
    raw_id = (params.get("node-id") or params.get("node_id") or [""])[0]
    node_id = urllib.parse.unquote(raw_id).replace("-", ":")
    return file_key, node_id


def _simplify_node(node: dict, depth: int = 0) -> dict:
    """Reduce a Figma node to fields useful for component spec extraction."""
    keep = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
    }
    # Geometry
    if "absoluteBoundingBox" in node:
        b = node["absoluteBoundingBox"]
        keep["size"] = {"w": round(b.get("width", 0)), "h": round(b.get("height", 0))}
    # Text
    if node.get("type") == "TEXT" and "characters" in node:
        keep["text"] = node["characters"]
        if "style" in node:
            s = node["style"]
            keep["textStyle"] = {
                k: s[k] for k in ("fontFamily", "fontWeight", "fontSize", "textAlignHorizontal")
                if k in s
            }
    # Fill colours
    fills = [
        f for f in node.get("fills", [])
        if f.get("type") == "SOLID" and f.get("visible", True)
    ]
    if fills:
        c = fills[0].get("color", {})
        keep["fill"] = "#{:02x}{:02x}{:02x}".format(
            round(c.get("r", 0) * 255),
            round(c.get("g", 0) * 255),
            round(c.get("b", 0) * 255),
        )
    # Component / variant info
    if "componentId" in node:
        keep["componentId"] = node["componentId"]
    if "variantProperties" in node:
        keep["variants"] = node["variantProperties"]
    # Recurse children up to depth 5 (keeps output manageable)
    if depth < 5 and "children" in node:
        keep["children"] = [_simplify_node(c, depth + 1) for c in node["children"]]
    return keep


class FigmaReaderInput(BaseModel):
    operation: str = Field(
        description=(
            "Operation to perform. One of:\n"
            "  get_frame   — return the component/frame tree as simplified JSON\n"
            "  get_tokens  — return design styles (colours, typography) as a token map\n"
            "  get_image   — return the rendered PNG URL for the frame"
        )
    )
    url: str = Field(
        description=(
            "Figma URL for the file or specific frame. "
            "Copy from the browser address bar while viewing the design. "
            "Include the ?node-id=... query parameter to target a specific frame."
        )
    )


class FigmaReaderTool(BaseTool):
    name: str = "figma_reader"
    description: str = (
        "Read Figma design data: fetch a frame's component tree, extract design tokens "
        "(colours, typography, spacing), or get a rendered image URL for visual comparison. "
        "Requires a Figma URL from the ticket or design link."
    )
    args_schema: type[BaseModel] = FigmaReaderInput

    def _run(self, operation: str, url: str) -> str:
        try:
            if operation == "get_frame":
                return self._get_frame(url)
            if operation == "get_tokens":
                return self._get_tokens(url)
            if operation == "get_image":
                return self._get_image(url)
            return f"Unknown operation '{operation}'. Use: get_frame, get_tokens, get_image."
        except (ValueError, RuntimeError) as exc:
            return f"ERROR: {exc}"

    def _get_frame(self, url: str) -> str:
        file_key, node_id = _parse_figma_url(url)
        if node_id:
            data = _figma_get(f"/v1/files/{file_key}/nodes?ids={urllib.parse.quote(node_id)}")
            nodes = data.get("nodes", {})
            if not nodes:
                return "No nodes found for the given node-id."
            node = next(iter(nodes.values())).get("document", {})
        else:
            # No node-id: return top-level page
            data = _figma_get(f"/v1/files/{file_key}?depth=3")
            pages = data.get("document", {}).get("children", [])
            node = pages[0] if pages else {}

        simplified = _simplify_node(node)
        return json.dumps(simplified, indent=2)

    def _get_tokens(self, url: str) -> str:
        file_key, _ = _parse_figma_url(url)
        data = _figma_get(f"/v1/files/{file_key}/styles")
        styles: list[dict] = data.get("meta", {}).get("styles", [])

        tokens: dict[str, Any] = {"colors": {}, "text": {}, "effects": {}}
        for style in styles:
            name = style.get("name", "unknown").replace("/", ".").replace(" ", "-").lower()
            style_type = style.get("style_type", "")
            if style_type == "FILL":
                tokens["colors"][name] = {"nodeId": style.get("node_id", "")}
            elif style_type == "TEXT":
                tokens["text"][name] = {"nodeId": style.get("node_id", "")}
            elif style_type == "EFFECT":
                tokens["effects"][name] = {"nodeId": style.get("node_id", "")}

        return json.dumps(tokens, indent=2)

    def _get_image(self, url: str) -> str:
        file_key, node_id = _parse_figma_url(url)
        if not node_id:
            return "ERROR: node-id required in URL to render a specific frame."
        encoded = urllib.parse.quote(node_id)
        data = _figma_get(f"/v1/images/{file_key}?ids={encoded}&format=png&scale=2")
        images: dict = data.get("images", {})
        # node_id key may use : or - depending on API version
        img_url = images.get(node_id) or images.get(node_id.replace(":", "-")) or ""
        if not img_url:
            return f"No image rendered for node {node_id}. Available: {list(images.keys())}"
        return f"Rendered frame PNG: {img_url}"
