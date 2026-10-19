"""Fictional three-status rehearsal data; the testing folders contain PDFs only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = {
    "vendor_name": "Blue Orchid Supplies Private Limited", "email": "vendor@example.test",
    "country": "India", "bank_account_holder": "Blue Orchid Supplies Private Limited",
    "bank_account_number": "000123456789",
}
TESTING_CASES = (
    {"case": "approved", "folder": "1_Approved", "expected": "APPROVED",
     "data": COMMON | {"tax_id": "29ABCDE1234F4ZT", "bank_name": "ICICI Bank", "ifsc_code": "ICIC0001234"},
     "gst_file": "GST_Registration_Certificate.pdf", "bank_file": "ICICI_Bank_Statement.pdf"},
    {"case": "pending", "folder": "2_Pending", "expected": "PENDING",
     "data": COMMON | {"tax_id": "29ABCDE1234F5ZS", "bank_name": "Axis Bank", "ifsc_code": "UTIB0001234"},
     "gst_file": "Tax_Invoice.pdf", "bank_file": "Axis_Bank_Statement.pdf"},
    {"case": "rejected", "folder": "3_Rejected", "expected": "REJECTED",
     "data": COMMON | {"tax_id": "29ABCDE1234F6ZR", "bank_name": "ICICI Bank", "ifsc_code": "ICIC0001234",
                       "bank_account_holder": "Different Synthetic Person"},
     "gst_file": "GST_Registration_Certificate.pdf", "bank_file": "ICICI_Bank_Statement.pdf"},
)


def fixture_manifest():
    return {"synthetic": True, "scenarios": [
        {"case": case["case"], "data": dict(case["data"]), "expected": case["expected"],
         "gst_path": str(ROOT / "testing" / case["folder"] / case["gst_file"]),
         "bank_path": str(ROOT / "testing" / case["folder"] / case["bank_file"])}
        for case in TESTING_CASES]}
