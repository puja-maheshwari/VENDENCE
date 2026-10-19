"""Export redacted evidence from the active synthetic browser-test store.

This reads SQLite only. It does not create applications, run validation, or
replace the separate observations made through the actual Streamlit browser.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{ROOT / 'database/vendence.db'}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    applications = []
    for row in connection.execute("SELECT submission_id,status,current_revision,decision_reason FROM vendor_submissions ORDER BY submission_id"):
        application = dict(row)
        sid = application["submission_id"]
        application["checks"] = [dict(check) for check in connection.execute(
            "SELECT revision,code,outcome,message FROM verification_checks WHERE submission_id=? ORDER BY check_id", (sid,))]
        application["documents"] = []
        for document in connection.execute(
                "SELECT document_id,document_type,file_name,revision,extracted_data FROM vendor_documents WHERE submission_id=? ORDER BY document_id", (sid,)):
            evidence = {key: document[key] for key in ("document_id", "document_type", "file_name", "revision")}
            extraction = json.loads(document["extracted_data"] or "{}")
            evidence["classification"] = {key: extraction.get(key, "") for key in ("document_type", "document_subtype")}
            application["documents"].append(evidence)
        application["revision_count"] = connection.execute(
            "SELECT COUNT(*) FROM submission_revisions WHERE submission_id=?", (sid,)).fetchone()[0]
        application["event_count"] = connection.execute(
            "SELECT COUNT(*) FROM processing_events WHERE submission_id=?", (sid,)).fetchone()[0]
        applications.append(application)
    report = {"exported_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Read-only snapshot of active synthetic browser test records. Browser observations are separate.",
              "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
              "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
              "applications": applications}
    connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(f"Exported {len(applications)} application summaries; database integrity: {report['integrity_check']}.")


if __name__ == "__main__":
    main()
