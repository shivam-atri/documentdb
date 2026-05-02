#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def summarize(report: dict) -> str:
    findings = report.get('findings', [])
    sev = {'high': 0, 'medium': 0, 'low': 0}
    for f in findings:
        s = f.get('severity', 'low')
        if s in sev:
            sev[s] += 1
    return f"Findings: high={sev['high']} medium={sev['medium']} low={sev['low']} total={len(findings)}"


def tool_status(report: dict) -> str:
    lines = []
    for t in report.get('deterministic_tools', []):
        rc = t.get('returncode', 0)
        status = 'ok' if rc == 0 else ('missing' if rc == 127 else f'rc={rc}')
        lines.append(f"- {t.get('cmd')}: {status}")
    return "\n".join(lines)


def top_findings(report: dict, n: int = 5) -> str:
    out = []
    for i, f in enumerate(report.get('findings', [])[:n], 1):
        out.append(
            f"{i}. [{f.get('severity')}] {f.get('file')}:{f.get('line')} {f.get('symbol')} | impacted={f.get('impacted')}"
        )
    return "\n".join(out) if out else "No findings."


def format_claude(report: dict) -> str:
    return (
        "You are reviewing a PR using structured static-analysis context.\n\n"
        f"{summarize(report)}\n\n"
        "Deterministic tools:\n"
        f"{tool_status(report)}\n\n"
        "Top findings:\n"
        f"{top_findings(report)}\n\n"
        "Task: validate correctness/performance/security/test coverage for each finding,"
        " reduce false positives, and suggest exact code/test changes."
    )


def format_chatgpt(report: dict) -> str:
    return (
        "Use this repo-specific review context to produce a merge recommendation.\n\n"
        f"{summarize(report)}\n\n"
        "Tool results:\n"
        f"{tool_status(report)}\n\n"
        "Top findings:\n"
        f"{top_findings(report)}\n\n"
        "Output sections: Risks, Evidence, Suggested Fixes, Required Tests, Final Verdict."
    )


def format_github(report: dict) -> str:
    return (
        "## Automated Review Summary\n"
        f"{summarize(report)}\n\n"
        "### Tool Status\n"
        f"{tool_status(report)}\n\n"
        "### Top Findings\n"
        f"{top_findings(report)}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', required=True)
    ap.add_argument('--format', choices=['claude', 'chatgpt', 'github'], required=True)
    args = ap.parse_args()
    report = load_report(Path(args.report))
    if args.format == 'claude':
        print(format_claude(report))
    elif args.format == 'chatgpt':
        print(format_chatgpt(report))
    else:
        print(format_github(report))


if __name__ == '__main__':
    main()
