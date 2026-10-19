"""Opt-in real Gemini integration on fixed synthetic fixtures only.

Never include this in offline unit discovery. It sends a small number of calls
to the configured account, saves only synthetic extraction results locally,
and never prints credentials or extracted banking values.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import tomllib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import load_local_env
from ai_service import extract_document
from validation import check_document_evidence
from tools.testing_cases import TESTING_CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-only", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()
    load_local_env()
    key = os.environ.get("GEMINI_API_KEY")
    secrets = ROOT / ".streamlit/secrets.toml"
    if not key and secrets.is_file():
        key = tomllib.loads(secrets.read_text()).get("GEMINI_API_KEY")
    if not key:
        print("Gemini status: NOT_CONFIGURED"); return 2
    if args.list_models:
        from google import genai
        from google.genai import types
        client = None
        try:
            client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=15000, retry_options=types.HttpRetryOptions(attempts=1)))
            names = [m.name for m in client.models.list() if "flash" in (m.name or "") and "image" not in m.name and "tts" not in m.name and "live" not in m.name]
            print("Available Flash model identifiers:", json.dumps(names))
            return 0
        except Exception as error:
            code = getattr(error, "code", None)
            print("Model discovery failed:", type(error).__name__, code if isinstance(code, int) else "")
            return 1
        finally:
            if client:
                client.close()
    approved,pending,_=TESTING_CASES
    cases = [
        ("happy_gst", "GST_CERTIFICATE", approved["folder"]+"/"+approved["gst_file"], "GST_CERTIFICATE", "GST_REGISTRATION_CERTIFICATE"),
        ("happy_bank_pdf", "BANK_PROOF", approved["folder"]+"/"+approved["bank_file"], "BANK_PROOF", "BANK_STATEMENT"),
        ("incorrect_invoice", "GST_CERTIFICATE", pending["folder"]+"/"+pending["gst_file"], "OTHER", "OTHER"),
    ]
    if args.first_only:
        cases = cases[:1]
    results = []
    output = ROOT / "tmp/qa_runs" / ("gemini_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(parents=True, exist_ok=True)
    for name, kind, filename, expected, subtype in cases:
        path = ROOT / "testing" / filename
        if not path.is_file():
            print(name + ": MISSING_FIXTURE"); return 2
        extracted, error = extract_document(kind, path.read_bytes(),
                                            "application/pdf" if path.suffix == ".pdf" else "image/png", api_key=key, model=args.model)
        if error:
            print(name + ": " + error)
            results.append({"case": name, "passed": False, "error": error})
            # Do not hammer a broken network/key/quota with further calls.
            break
        passed = (expected is None or extracted["document_type"] == expected) and (subtype is None or extracted["document_subtype"] == subtype)
        entry = {"case": name, "passed": passed, "document_type": extracted["document_type"],
                 "document_subtype": extracted["document_subtype"], "authenticity": "NOT_VERIFIED"}
        if name in {"happy_gst", "happy_bank_pdf"}:
            data = dict(approved["data"])
            checks = check_document_evidence(kind, data, extracted)
            entry["comparisons_passed"] = all(c["outcome"] == "PASS" for c in checks)
            entry["passed"] = passed and entry["comparisons_passed"]
        (output / (name + ".json")).write_text(json.dumps(extracted, indent=2))
        results.append(entry)
        print(name + ": " + ("PASS" if entry["passed"] else "FAIL") + " | " + extracted["document_subtype"] + " | authenticity NOT_VERIFIED", flush=True)
    (output / "report.json").write_text(json.dumps(results, indent=2))
    print("Synthetic integration report:", output / "report.json")
    return 0 if len(results) == len(cases) and all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
