---
type: CrewAI Task
title: Documentation Area Summarization
description: >
  Read a documentation directory and produce a brief summary of each document found.
tags: [explore, summarize, docs]
agent: architect
expected_output: >
  One DOC_SUMMARY block per document. Ends with DOCS COMPLETE.
---

You are summarizing a documentation directory. Use `workspace_reader` to list and read
the documents inside.

For each document file (`.md`, `.rst`, `.txt`, `.adoc`) produce:

```
DOC_SUMMARY: <relative-path>
<One paragraph (3-5 sentences) describing what this document covers, its intended audience,
and any key decisions or requirements it records.>
DOC_SUMMARY COMPLETE
```

**Guidelines:**
- Read the first ~100 lines of each document — that is usually enough for a summary
- Skip generated files (changelogs with auto-generated entries, lock files, API reference dumps)
- If a directory contains subdirectories (e.g. `docs/adr/`, `docs/add/`), list what
  categories of documents exist and summarize the most important 3-5 files per category
- Do not try to read binary attachments or images

End with exactly:
```
DOCS COMPLETE
```
