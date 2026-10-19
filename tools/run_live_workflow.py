"""Explicit synthetic end-to-end run with real Gemini and isolated storage."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_local_env
from tools.testing_cases import TESTING_CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-consistency-demo", action="store_true", required=True)
    parser.add_argument("--resume-run", type=Path, help="Retry a Pending isolated live_workflow run; retain its original report")
    args = parser.parse_args()
    load_local_env()
    if args.resume_run:
        destination = args.resume_run.expanduser().resolve()
        if not destination.is_relative_to((ROOT / "tmp/qa_runs").resolve()) or not destination.name.startswith("live_workflow_") or not (destination / "database/vendence.db").is_file():
            parser.error("Resume only an existing isolated live_workflow directory under tmp/qa_runs.")
    else:
        destination = ROOT / "tmp/qa_runs" / ("live_workflow_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        destination.mkdir(parents=True, exist_ok=False)
    os.environ["VENDENCE_DATA_DIR"] = str(destination)
    key = os.environ.get("GEMINI_API_KEY")
    secrets = ROOT / ".streamlit/secrets.toml"
    if not key and secrets.is_file():
        key = tomllib.loads(secrets.read_text()).get("GEMINI_API_KEY")
    if not key:
        print("Gemini status: NOT_CONFIGURED"); return 2
    from workflow import process_application
    import database as db
    db.initialize_database()
    case = TESTING_CASES[0]
    data = dict(case["data"])
    class Upload:
        def __init__(self, path): self.path, self.name = path, path.name
        def getvalue(self): return self.path.read_bytes()
    folder = ROOT / "testing" / case["folder"]
    docs = {"GST_CERTIFICATE": Upload(folder / case["gst_file"]),
            "BANK_PROOF": Upload(folder / case["bank_file"])}
    options = {}
    if args.resume_run:
        current = db.get_submission(1)
        if not current or current["status"] != "PENDING":
            parser.error("Only a Pending isolated application can be retried.")
        data, docs = None, {}
        options = {"submission_id": 1, "expected_revision": current["current_revision"], "reprocess": True}
    result = process_application(data, docs, policy="demo_consistency", synthetic_declared=True,
                                 api_key=key, on_stage=lambda title, detail: print(title, flush=True), **options)
    report = {"submission_id": result.submission_id, "revision": result.revision,
              "status": result.status, "reason": result.reason, "error_code": result.error_code,
              "checks": len(result.checks), "all_checks_passed": all(c["outcome"] == "PASS" for c in result.checks),
              "authenticity": [db.get_authenticity(d["document_id"])["state"] for d in db.get_documents(result.submission_id)]}
    filename = ("retry_report_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json") if args.resume_run else "report.json"
    report_path = destination / filename
    report_path.write_text(json.dumps(report, indent=2))
    print("Workflow result:", result.status)
    print("Authenticity states:", ", ".join(report["authenticity"]))
    print("Integration report:", report_path)
    return 0 if result.status == "APPROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
