"""Opt-in real Gemini batch using fictional fixtures; emits redacted evidence.

Default storage is isolated below the output directory. --active-store is an
explicit choice to populate the local demonstration dashboard. No data is reset.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import tomllib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_local_env


class Upload:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name

    def getvalue(self):
        return self.path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--real-gemini", required=True, action="store_true")
    parser.add_argument("--active-store", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--resume", action="store_true", help="Retry failed Pending runs under their original IDs; preserve earlier attempts")
    args = parser.parse_args()
    load_local_env()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ["VENDENCE_DATA_DIR"] = str(ROOT if args.active_store else output / "store")
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("synthetic") is not True:
        parser.error("Only an explicitly synthetic fixture manifest is supported.")
    entries = [entry for entry in manifest["scenarios"] if not args.cases or entry["case"] in args.cases]
    if args.cases and set(args.cases) != {entry["case"] for entry in entries}:
        parser.error("A requested case is absent from the manifest.")
    expanded = []
    for entry in entries:
        expanded.append(entry)
        if entry["case"] == "gemini_failure":
            expanded.append({**entry, "case": "gemini_recovery", "expected": "APPROVED", "reprocess_case": "gemini_failure"})
    entries = expanded
    key = os.environ.get("GEMINI_API_KEY")
    if not key and (ROOT / ".streamlit/secrets.toml").is_file():
        key = tomllib.loads((ROOT / ".streamlit/secrets.toml").read_text()).get("GEMINI_API_KEY")
    if not key:
        parser.error("Configure Gemini locally before running integration tests.")
    import database as db
    from workflow import process_application
    from validation import required_check_codes
    db.initialize_database()
    report_path = output / "backend_batch.json"
    if report_path.exists():
        if not args.resume:
            parser.error("Choose a new output directory or explicitly --resume; earlier attempts are retained.")
        report = json.loads(report_path.read_text())
        if report.get("manifest") != str(args.manifest.resolve()):
            parser.error("Resume requires the original manifest.")
    else:
        report = {"started_at": datetime.now(timezone.utc).isoformat(), "interface": "workflow backend",
                  "synthetic": True, "manifest": str(args.manifest.resolve()), "results": []}
    for entry in entries:
        case = entry["case"]
        policy = entry.get("policy", "demo_consistency")
        uploads = {kind: Upload(entry[key_name]) if entry.get(key_name) else None
                   for kind, key_name in (("GST_CERTIFICATE", "gst_path"), ("BANK_PROOF", "bank_path"))}
        controlled_outage = case == "gemini_failure"
        previous = next((row for row in reversed(report["results"]) if row["case"] == case), None)
        if previous and previous["passed"]:
            continue
        options = {}
        if previous:
            current = db.get_submission(previous["submission_id"])
            if not current or current["status"] != "PENDING":
                parser.error("A retry requires the original Pending application in this store.")
            options = {"submission_id": current["submission_id"], "expected_revision": current["current_revision"], "reprocess": True}
            uploads = {}
        elif entry.get("reprocess_case"):
            original = next(row for row in reversed(report["results"]) if row["case"] == entry["reprocess_case"])
            current = db.get_submission(original["submission_id"])
            if not current or current["status"] != "PENDING":
                parser.error("Outage recovery requires its original Pending application.")
            options = {"submission_id": current["submission_id"], "expected_revision": current["current_revision"], "reprocess": True}
            uploads = {}
        context = (patch("workflow.extract_document", return_value=(None, "Controlled integration test: Gemini unavailable."))
                   if controlled_outage else nullcontext())
        print("Running:", case, flush=True)
        start = time.monotonic()
        with context:
            result = process_application(entry["data"], uploads, policy=policy,
                                         synthetic_declared=policy == "demo_consistency", api_key=key, **options)
        errors = [c["code"] for c in result.checks if c["outcome"] == "ERROR"]
        documents = db.get_documents(result.submission_id) if result.submission_id else []
        record = {"case": case, "submission_id": result.submission_id, "revision": result.revision,
                  "expected": entry["expected"], "actual": result.status, "policy": policy,
                  "duration_seconds": round(time.monotonic() - start, 2), "reason": result.reason,
                  "controlled_outage": controlled_outage, "error_code": result.error_code,
                  "error_checks": errors, "check_count": len(result.checks),
                  "documents": [{"kind": d["document_type"], "sha256": d["sha256"],
                                 "classification": json.loads(d["extracted_data"] or "{}").get("document_subtype"),
                                 "authenticity": db.get_authenticity(d["document_id"])["state"]} for d in documents]}
        complete = {c["code"] for c in result.checks} == required_check_codes(policy)
        persisted = result.submission_id is not None and db.get_submission(result.submission_id)["status"] == result.status
        files_ok = all(Path(d["file_path"]).is_file() and hashlib.sha256(Path(d["file_path"]).read_bytes()).hexdigest() == d["sha256"] for d in documents)
        record["passed"] = (result.status == entry["expected"] and not result.error_code and
                            (controlled_outage or not errors) and complete and persisted and files_ok)
        report["results"].append(record)
        report_path.write_text(json.dumps(report, indent=2))
        print(f"{case}: {result.status}; {'PASS' if record['passed'] else 'FAIL'}; application {result.submission_id}", flush=True)
        if not record["passed"]:
            print("Stopped at the failed boundary. Review:", report_path)
            return 1
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    latest = {row["case"]: row for row in report["results"]}
    report["all_passed"] = all(row["passed"] for row in latest.values())
    report_path.write_text(json.dumps(report, indent=2))
    print("Batch evidence:", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
