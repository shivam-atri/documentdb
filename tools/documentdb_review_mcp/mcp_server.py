#!/usr/bin/env python3
"""Provider-neutral MCP server for review pipeline tools."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("documentdb-review-mcp")
ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "review_pipeline.py"
RENDER = ROOT / "render_for_llm.py"


def _run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


@mcp.tool()
def index_repo(repo: str, out: str) -> str:
    return json.dumps(_run(["python3", str(PIPELINE), "index", "--repo", repo, "--out", out]))


@mcp.tool()
def review_diff(repo: str, out: str, base: str, head: str) -> str:
    return json.dumps(_run(["python3", str(PIPELINE), "review", "--repo", repo, "--out", out, "--base", base, "--head", head]))


@mcp.tool()
def render_review(report: str, format: str = "claude") -> str:
    res = _run(["python3", str(RENDER), "--report", report, "--format", format])
    return res["stdout"] if res["returncode"] == 0 else json.dumps(res)


if __name__ == "__main__":
    mcp.run()
