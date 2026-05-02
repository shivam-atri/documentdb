import json
import subprocess


def test_index_outputs_sqlite_and_json():
    subprocess.check_call([
        "python3", "tools/documentdb_review_mcp/review_pipeline.py", "index",
        "--repo", "tools/documentdb_review_mcp/demo_project", "--out", ".cache/review_mcp_demo_test"
    ])
    with open('.cache/review_mcp_demo_test/python_index.json', 'r', encoding='utf-8') as f:
        payload = json.load(f)
    assert 'files' in payload


def test_review_output_schema():
    # create tiny git history in demo project
    subprocess.check_call("cd tools/documentdb_review_mcp/demo_project && git init -q && git config user.email demo@example.com && git config user.name demo && git add . && git commit -qm init && echo '# test change' >> services/users/service.py && git add services/users/service.py && git commit -qm change", shell=True)
    try:
        subprocess.check_call([
            "python3", "tools/documentdb_review_mcp/review_pipeline.py", "review",
            "--repo", "tools/documentdb_review_mcp/demo_project", "--out", ".cache/review_mcp_demo_test",
            "--base", "HEAD~1", "--head", "HEAD"
        ])
        with open('.cache/review_mcp_demo_test/review_report.json', 'r', encoding='utf-8') as f:
            report = json.load(f)
        assert 'findings' in report
        assert 'deterministic_tools' in report
        assert 'llm_review_input' in report
        assert 'findings_context' in report['llm_review_input']
    finally:
        subprocess.call(['rm', '-rf', 'tools/documentdb_review_mcp/demo_project/.git'])
