# MCP integrations (Claude + other MCP clients)

This is **not Claude-only** now.
Use the provider-neutral MCP server:
- `tools/documentdb_review_mcp/mcp_server.py`

Claude-specific wrapper:
- `tools/documentdb_review_mcp/claude_mcp_server.py`

## Why render?
`render_for_llm.py` is used when your workflow expects plain text prompts/comments instead of tool calls.
- MCP-native flow: call `index_repo/review_diff/render_review` tools directly.
- Non-MCP flow: render `review_report.json` to concise prompt text for ChatGPT/Claude/GitHub comment bots.

## Generic MCP client config

```json
{
  "mcpServers": {
    "documentdb-review": {
      "command": "python3",
      "args": ["/absolute/path/to/tools/documentdb_review_mcp/mcp_server.py"]
    }
  }
}
```

## Native tools
- `index_repo(repo, out)`
- `review_diff(repo, out, base, head)`
- `render_review(report, format)`

## Example output (review_report.json excerpt)

```json
{
  "storage": ".cache/review_mcp_demo/review_index.db",
  "rag_enabled": true,
  "findings": [
    {
      "file": "services/users/service.py",
      "line": 10,
      "symbol": "UsersHandler.do_GET",
      "severity": "low",
      "impacted": {"callers": [], "imported_dependents": [], "service_dependents": []}
    }
  ]
}
```
