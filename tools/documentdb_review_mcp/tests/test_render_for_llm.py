import json
import subprocess
from pathlib import Path


def _write_report(tmp_path: Path) -> Path:
    report = {
        "deterministic_tools": [{"cmd": "ruff check .", "returncode": 0}],
        "findings": [{"severity": "medium", "file": "a.py", "line": 10, "symbol": "foo", "impacted": {"callers": ["bar"]}}],
    }
    p = tmp_path / "report.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    return p


def test_render_claude(tmp_path: Path):
    report = _write_report(tmp_path)
    out = subprocess.check_output([
        "python3", "tools/documentdb_review_mcp/render_for_llm.py", "--report", str(report), "--format", "claude"
    ], text=True)
    assert "Findings:" in out
    assert "Top findings:" in out


def test_render_github(tmp_path: Path):
    report = _write_report(tmp_path)
    out = subprocess.check_output([
        "python3", "tools/documentdb_review_mcp/render_for_llm.py", "--report", str(report), "--format", "github"
    ], text=True)
    assert "Automated Review Summary" in out
