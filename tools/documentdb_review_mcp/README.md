# documentdb_review_mcp (end-to-end demo)

Python-first end-to-end code review pipeline demo with service dependency awareness, local storage, and RAG retrieval.

## Are we using RAG/vector index?
Yes.
- RAG retrieval is enabled during review (`rag_context` in findings) using token retrieval from local index tables.
- `vector_docs` are persisted to local SQLite for downstream vector DB ingestion.

## Storage for large codebases
Index data is written to local SQLite (`review_index.db`) instead of only in-memory/json:
- files, symbols, edges (import/call/inheritance/service)
- chunks
- tokens (lexical)
- vector_docs

## Included multi-service dummy project
`tools/documentdb_review_mcp/demo_project` includes gateway/users/orders services.

Run services:
```bash
tools/documentdb_review_mcp/demo_project/run_demo.sh
```

Index + review:
```bash
python3 tools/documentdb_review_mcp/review_pipeline.py index --repo tools/documentdb_review_mcp/demo_project --out .cache/review_mcp_demo
python3 tools/documentdb_review_mcp/review_pipeline.py review --repo tools/documentdb_review_mcp/demo_project --out .cache/review_mcp_demo --base HEAD~1 --head HEAD
```

Artifacts:
- `.cache/review_mcp_demo/python_index.json`
- `.cache/review_mcp_demo/review_index.db`
- `.cache/review_mcp_demo/review_report.json`

## LLM integration (Claude / ChatGPT)

Render report into prompt-ready text:

```bash
python3 tools/documentdb_review_mcp/render_for_llm.py --report .cache/review_mcp_demo/review_report.json --format claude
python3 tools/documentdb_review_mcp/render_for_llm.py --report .cache/review_mcp_demo/review_report.json --format chatgpt
python3 tools/documentdb_review_mcp/render_for_llm.py --report .cache/review_mcp_demo/review_report.json --format github
```

See `tools/documentdb_review_mcp/integrations.md` for integration flow and Greptile comparison.

## Native Claude integration (MCP server)

A native Claude MCP server is included:
- `tools/documentdb_review_mcp/claude_mcp_server.py`

It exposes tools directly in Claude:
- `index_repo(repo, out)`
- `review_diff(repo, out, base, head)`
- `render_review(report, format)`

See `tools/documentdb_review_mcp/integrations.md` for Claude Desktop config.

## Not Claude-only

Use `mcp_server.py` for any MCP-compatible client. `claude_mcp_server.py` is only a convenience wrapper.

## Example output

`review_report.json` includes:
- `storage` (SQLite file path)
- `rag_enabled`
- `deterministic_tools`
- `findings` (file/line/symbol/severity/impacted/rag_context)

See `integrations.md` for a concrete JSON excerpt.

## About `review` behavior

`review` currently does two things:
1. deterministic/static pass (symbol + graph + dependency heuristics + tool outputs)
2. emits `llm_review_input` (structured context pack + system prompt) so you can feed directly into an LLM for deeper reasoning.

So yes — feeding what we built to the LLM directly is supported through `llm_review_input` in `review_report.json`.
