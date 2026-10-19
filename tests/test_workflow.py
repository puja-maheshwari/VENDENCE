"""Seven required scenarios and technical failures, isolated from vendor data."""
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

import database as db
import workflow
from ai_service import EXTRACTION_FIELDS
from validation import gstin_check_digit


DATA = {
    "vendor_name": "Blue Orchid Supplies Private Limited", "email": "vendor@example.test",
    "country": "India", "tax_id": "29ABCDE1234F1Z" + gstin_check_digit("29ABCDE1234F1Z"),
    "bank_name": "Example Demonstration Bank", "bank_account_holder": "Blue Orchid Supplies Private Limited",
    "bank_account_number": "000123456789", "ifsc_code": "EXMP0001234",
}


class Upload:
    def __init__(self, label="synthetic", content=None):
        self.name = f"{label}.png"
        if content is None:
            image = Image.new("RGB", (800, 300), "white")
            ImageDraw.Draw(image).text((20, 30), label + " - synthetic demonstration only", fill="black")
            buffer = BytesIO(); image.save(buffer, format="PNG"); content = buffer.getvalue()
        self.content = content
    def getvalue(self):
        return self.content


def extraction(document_type, **changes):
    values = {field: "" for field in EXTRACTION_FIELDS}
    values.update({"document_type": document_type, "classification_evidence": "Synthetic demonstration evidence"})
    if document_type == "GST_CERTIFICATE":
        values.update(document_subtype="GST_REGISTRATION_CERTIFICATE", document_title="Registration Certificate",
                      registration_form="GST REG-06", legal_name=DATA["vendor_name"], gstin=DATA["tax_id"],
                      trade_name="Blue Orchid")
    else:
        values.update(document_subtype="BANK_ACCOUNT_CONFIRMATION", document_title="Bank Account Confirmation",
                      account_holder=DATA["bank_account_holder"], account_number=DATA["bank_account_number"],
                      ifsc=DATA["ifsc_code"], bank_name=DATA["bank_name"])
    values.update(changes)
    return values


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(db, DB_PATH=self.root / "database/test.db", UPLOAD_DIR=self.root / "uploads")
        self.paths.start(); self.addCleanup(self.paths.stop); self.addCleanup(self.temp.cleanup)
        db.initialize_database()
        self.ai = patch("workflow.extract_document", side_effect=lambda kind, *args, **kwargs: (extraction(kind), None)).start()
        self.addCleanup(patch.stopall)

    def submit(self, data=None, docs=None, **kwargs):
        kwargs.setdefault("policy", "demo_consistency"); kwargs.setdefault("synthetic_declared", True)
        return workflow.process_application(data or DATA.copy(),
                                            docs if docs is not None else {kind: Upload(kind) for kind in workflow.DOCUMENT_TYPES},
                                            **kwargs)

    def test_scenario_1_explicit_synthetic_happy_path(self):
        result = self.submit()
        self.assertEqual(result.status, "APPROVED", result.reason)
        self.assertTrue(all(c["outcome"] == "PASS" for c in result.checks))
        self.assertIn("synthetic", result.reason)
        self.assertIn("NOT_VERIFIED", result.reason)
        self.assertEqual(db.get_submission(result.submission_id)["status"], "APPROVED")
        self.assertTrue(all(db.get_authenticity(d["document_id"])["state"] == "NOT_VERIFIED"
                            for d in db.get_documents(result.submission_id)))

    def test_incomplete_backend_submission_groups_causes_and_retains_all_checks(self):
        result = self.submit(data={key: "INVALID" if key == "tax_id" else "" for key in DATA}, docs={})
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reason.count("Missing required information:"), 1)
        self.assertIn("GSTIN structure is invalid", result.reason)
        self.assertNotIn("Missing mandatory field:", result.reason)
        self.assertNotIn("could not be checked until", result.reason)
        self.assertNotIn("checks will continue", result.reason)
        self.assertNotIn("IFSC must contain", result.reason)
        self.assertEqual(len(result.checks), len(workflow.required_check_codes("demo_consistency")))
        self.assertEqual(len(db.get_checks(result.submission_id)), len(result.checks))

    def test_scenario_2_infographic_is_pending_and_requests_documents(self):
        self.ai.side_effect = lambda kind, *a, **k: (extraction(kind) | {"document_type": "OTHER", "document_subtype": "GSTIN_INFOGRAPHIC"}
                                                   if kind == "GST_CERTIFICATE" else extraction(kind), None)
        result = self.submit()
        self.assertEqual(result.status, "PENDING")
        self.assertIn("The uploaded GST certificate is invalid.", result.reason)
        self.assertNotIn("educational GSTIN infographic", result.reason)
        self.assertIn("Form GST REG-06", result.reason)
        self.assertNotIn("This required check could not be completed", result.reason)

    def test_scenario_3_bank_holder_mismatch(self):
        result = self.submit(data=DATA | {"bank_account_holder": "Different Synthetic Person"})
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any(c["code"] == "SUBMITTED_BANK_HOLDER" and c["outcome"] == "PENDING" for c in result.checks))
        self.assertTrue(any(c["code"] == "BANK_PROOF_BANK_ACCOUNT_HOLDER_MATCH" and c["outcome"] == "REJECTED" for c in result.checks))
        self.assertIn("Correct the name or upload matching bank proof", result.reason)
        self.assertNotIn("Human review required", result.reason)

    def test_company_name_difference_alone_remains_pending_when_bank_holder_matches(self):
        self.ai.side_effect = lambda kind, *a, **kw: (extraction(kind, **({"account_holder": "Different Synthetic Person"} if kind == "BANK_PROOF" else {})), None)
        result = self.submit(data=DATA | {"bank_account_holder": "Different Synthetic Person"})
        self.assertEqual(result.status, "PENDING")
        self.assertEqual(next(c["outcome"] for c in result.checks if c["code"] == "BANK_PROOF_BANK_ACCOUNT_HOLDER_MATCH"), "PASS")

    def test_selected_bank_must_match_uploaded_bank_evidence(self):
        self.ai.side_effect = lambda kind, *a, **k: (extraction(kind) | {"bank_name": "ICICI Bank"}
                                                   if kind == "BANK_PROOF" else extraction(kind), None)
        result = self.submit(data=DATA | {"bank_name": "HDFC Bank"})
        self.assertEqual(result.status, "PENDING")
        check = next(c for c in result.checks if c["code"] == "BANK_PROOF_BANK_NAME_MATCH")
        self.assertEqual(check["outcome"], "PENDING")
        self.assertIn("Bank name differs", check["message"])

    def test_bank_suffix_variations_pass_without_changing_company_name_rules(self):
        self.ai.side_effect = lambda kind, *a, **k: (extraction(kind) | {"bank_name": "HDFC BANK LTD."}
                                                   if kind == "BANK_PROOF" else extraction(kind), None)
        result = self.submit(data=DATA | {"bank_name": "HDFC Bank"})
        self.assertEqual(result.status, "APPROVED", result.reason)
        self.assertTrue(all(c["outcome"] == "PASS" for c in result.checks))

    def test_scenario_4_approved_duplicate_with_whitespace(self):
        first = self.submit(); self.assertEqual(first.status, "APPROVED", first.reason)
        second = self.submit(data=DATA | {"tax_id": " 29 abCDe 1234 f1z w "})
        self.assertEqual(second.status, "REJECTED", second.reason)
        self.assertIn(f"VND-{first.submission_id:06d}", second.reason)

    def test_scenario_5_correction_preserves_id_and_audit(self):
        first = self.submit(data=DATA | {"bank_account_holder": "Different Synthetic Person"})
        self.assertEqual(first.status, "REJECTED")
        old_docs = db.get_documents(first.submission_id)
        second = self.submit(submission_id=first.submission_id, expected_revision=1,
                             correction_reason="Corrected account holder")
        self.assertEqual(second.status, "APPROVED", second.reason)
        self.assertEqual(second.submission_id, first.submission_id)
        self.assertEqual(second.revision, 2)
        self.assertEqual(len(db.get_revisions(first.submission_id)), 2)
        self.assertTrue(all(Path(doc["file_path"]).is_file() for doc in old_docs))
        self.assertGreater(len(db.get_documents(first.submission_id, include_history=True)), len(old_docs))
        self.assertIn("RESUBMISSION_RECEIVED", [e["stage"] for e in db.get_events(first.submission_id)])
        self.assertEqual(db.get_checks(first.submission_id), [dict(c, created_at=db.get_checks(first.submission_id)[i]["created_at"])
                                                             for i, c in enumerate(second.checks)])

    def test_scenario_6_fabricated_matching_certificate_strict_pending(self):
        result = self.submit(policy="strict", synthetic_declared=False)
        self.assertEqual(result.status, "PENDING")
        self.assertIn("NOT_VERIFIED", result.reason)
        self.assertTrue(any(c["code"] == "GST_CERTIFICATE_IDENTITY" and c["outcome"] == "PASS" for c in result.checks))
        self.assertTrue(all(db.get_authenticity(d["document_id"])["state"] == "NOT_VERIFIED"
                            for d in db.get_documents(result.submission_id)))

    def test_scenario_7_gemini_outage(self):
        self.ai.side_effect = None; self.ai.return_value = (None, "Gemini extraction failed: TimeoutError")
        result = self.submit()
        self.assertEqual(result.status, "PENDING")
        events = db.get_events(result.submission_id)
        self.assertTrue(any(e["outcome"] == "ERROR" and "AI_EXTRACTION" in e["stage"] for e in events))
        self.assertIn("GST certificate comparisons could not run", result.reason)
        self.assertIn("Bank proof comparisons could not run", result.reason)
        self.assertIn("a technical failure alone does not require replacing the document", result.reason)

    def test_omitted_document_categories_cannot_bypass_requirements(self):
        result = self.submit(docs={})
        self.assertEqual(result.status, "PENDING")
        self.ai.assert_not_called()
        self.assertTrue(all(any(c["code"] == f"{kind}_UPLOAD" and c["outcome"] == "PENDING" for c in result.checks)
                            for kind in workflow.DOCUMENT_TYPES))

    def test_correction_without_replacement_reuses_valid_evidence(self):
        first = self.submit(data=DATA | {"email": "invalid"})
        count = self.ai.call_count
        second = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1)
        self.assertEqual(second.status, "APPROVED", second.reason)
        self.assertEqual(self.ai.call_count, count)

    def test_invalid_replacement_cannot_fall_back_to_old_document(self):
        first = self.submit(data=DATA | {"email": "invalid"})
        second = self.submit(docs={"GST_CERTIFICATE": Upload(content=b"invalid")},
                             submission_id=first.submission_id, expected_revision=1)
        self.assertEqual(second.status, "PENDING")
        retry = self.submit(docs={}, submission_id=first.submission_id, expected_revision=2, reprocess=True)
        self.assertEqual(retry.status, "PENDING")
        self.assertNotIn("GST_CERTIFICATE", {d["document_type"] for d in db.get_documents(first.submission_id)})

    def test_missing_saved_document_blocks_reprocessing(self):
        first = self.submit(policy="strict")
        Path(db.get_documents(first.submission_id)[0]["file_path"]).unlink()
        second = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1, reprocess=True)
        self.assertEqual(second.status, "PENDING")
        self.assertTrue(any(c["outcome"] == "ERROR" for c in second.checks))

    def test_invalid_ai_result_ends_safely_with_audit(self):
        self.ai.side_effect = None; self.ai.return_value = ({"document_type": "GST_CERTIFICATE"}, None)
        result = self.submit()
        self.assertEqual(result.status, "PENDING")
        self.assertEqual(result.error_code, "ValueError")
        self.assertEqual(db.get_submission(result.submission_id)["status"], "PENDING")
        self.assertIn("PROCESSING_ERROR", [e["stage"] for e in db.get_events(result.submission_id)])

    def test_database_creation_failure_no_submission_or_approval_claim(self):
        with patch("workflow.db.create_vendor_submission", side_effect=OSError("secret database details")):
            result = self.submit()
        self.assertIsNone(result.submission_id)
        self.assertEqual(result.status, "PENDING")
        self.assertNotIn("secret", result.reason)

    def test_document_save_failure_persisted_pending(self):
        with patch("workflow.db.save_document", side_effect=OSError("storage unavailable")):
            result = self.submit()
        self.assertEqual(result.status, "PENDING")
        self.assertEqual(db.get_submission(result.submission_id)["status"], "PENDING")


    def test_stale_resubmission_does_not_overwrite_current_application(self):
        first = self.submit(policy="strict")
        second = self.submit(submission_id=first.submission_id, expected_revision=1, policy="strict")
        stale = self.submit(submission_id=first.submission_id, expected_revision=1)
        self.assertEqual(stale.error_code, "ConcurrentUpdateError")
        self.assertEqual(db.get_submission(first.submission_id)["current_revision"], second.revision)

    def test_review_and_reprocess_strict_uses_recorded_evidence(self):
        first = self.submit(policy="strict")
        for doc in db.get_documents(first.submission_id):
            db.record_authenticity(doc["document_id"], "VERIFIED", "AUTHORIZED_REVIEW", "Test reviewer",
                                   "SIMULATED_TEST_EVIDENCE_ONLY", "This is a unit-test attestation, not real verification.")
        second = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1, reprocess=True, policy="strict")
        self.assertEqual(second.status, "APPROVED", second.reason)

    def test_failed_review_prevents_reapproval_with_reused_ai_extraction(self):
        first = self.submit()
        self.assertEqual(first.status, "APPROVED")
        doc = db.get_documents(first.submission_id)[0]
        db.record_authenticity(doc["document_id"], "VERIFICATION_FAILED", "AUTHORIZED_REVIEW",
                               "Synthetic Test Reviewer", "SIMULATED_FAILURE_ONLY")
        self.ai.reset_mock()
        second = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1, reprocess=True)
        self.assertEqual(second.status, "PENDING")
        self.assertIn("Independent authenticity verification failed", second.reason)
        self.ai.assert_not_called()

    def test_approval_withdrawal_returns_pending_requirements(self):
        first = self.submit(); self.assertEqual(first.status, "APPROVED")
        doc = db.get_documents(first.submission_id)[0]
        result = workflow.record_document_review(first.submission_id, document_id=doc["document_id"],
            state="VERIFICATION_FAILED", method="AUTHORIZED_REVIEW", reviewer="Synthetic Test Reviewer",
            evidence_reference="SIMULATED_REVIEW_ONLY")
        self.assertEqual(result.status, "PENDING")


    def test_review_cannot_target_document_from_another_application(self):
        first = self.submit(policy="strict")
        second = self.submit(data=DATA | {"tax_id": "DIFFERENT_SYNTHETIC_ID"}, policy="strict")
        document = db.get_documents(second.submission_id)[0]
        with self.assertRaises(db.ConcurrentUpdateError):
            workflow.record_document_review(first.submission_id, document_id=document["document_id"],
                state="VERIFICATION_FAILED", method="AUTHORIZED_REVIEW", reviewer="Synthetic Test Reviewer",
                evidence_reference="SIMULATED_REVIEW_ONLY")
        self.assertEqual(db.get_authenticity(document["document_id"])["state"], "NOT_VERIFIED")
        self.assertEqual(second.status, "REJECTED")

    def test_audit_does_not_contain_banking_values(self):
        result = self.submit()
        self.assertNotIn(DATA["bank_account_number"], json.dumps(db.get_events(result.submission_id)))

    def test_happy_path_needs_no_mail_settings_or_network(self):
        stages = []
        with patch.dict(os.environ, {}, clear=True), patch("socket.socket.connect", side_effect=AssertionError("Unexpected network access")):
            result = self.submit(on_stage=lambda title, detail: stages.append(title))
        self.assertEqual(result.status, "APPROVED", result.reason)
        self.assertEqual(len(result.checks), 33)
        self.assertNotIn("COMMUNICATION_RECEIPT", {c["code"] for c in result.checks})
        self.assertFalse(any("notification" in title.lower() for title in stages))
        self.assertTrue(any(e["stage"] == "FINAL_DECISION" for e in db.get_events(result.submission_id)))

    def test_invalid_gstin_rejected_and_correctable_under_same_id(self):
        first = self.submit(data=DATA | {"tax_id": "INVALID-GSTIN"})
        self.assertEqual(first.status, "REJECTED")
        self.assertIn("GSTIN structure", first.reason)
        second = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1)
        self.assertEqual(second.status, "APPROVED", second.reason)
        self.assertEqual(second.submission_id, first.submission_id)
        self.assertEqual(second.revision, 2)
        self.assertEqual(len(db.get_revisions(first.submission_id)), 2)

    def test_invalid_checksum_rejected_and_missing_gstin_pending(self):
        invalid = self.submit(data=DATA | {"tax_id": DATA["tax_id"][:-1] + "0"})
        self.assertEqual(invalid.status, "REJECTED")
        self.assertIn("GSTIN checksum", invalid.reason)
        missing = self.submit(data=DATA | {"tax_id": ""})
        self.assertEqual(missing.status, "PENDING")

    def test_invalid_contact_and_bank_formats_are_rejected(self):
        for field, value, code in (("email", "invalid-address", "EMAIL_FORMAT"),
                                   ("ifsc_code", "EXMP1001234", "IFSC_FORMAT"),
                                   ("bank_account_number", "123", "ACCOUNT_NUMBER_FORMAT")):
            with self.subTest(field=field):
                result = self.submit(data=DATA | {field: value})
                self.assertEqual(result.status, "REJECTED", result.reason)
                self.assertEqual(next(c["outcome"] for c in result.checks if c["code"] == code), "REJECTED")
                self.assertEqual(db.get_submission(result.submission_id)["status"], "REJECTED")

    def test_missing_contact_and_bank_values_remain_pending(self):
        result = self.submit(data=DATA | {"email": "", "ifsc_code": "", "bank_account_number": ""})
        self.assertEqual(result.status, "PENDING")
        for code in ("EMAIL_FORMAT", "IFSC_FORMAT", "ACCOUNT_NUMBER_FORMAT"):
            self.assertEqual(next(c["outcome"] for c in result.checks if c["code"] == code), "PENDING")

    def test_pending_duplicate_rejected_and_original_correction_is_allowed(self):
        original = self.submit(data=DATA | {"bank_account_holder": "Blue Orchid Supplies"})
        self.assertEqual(original.status, "PENDING")
        duplicate = self.submit(data=DATA | {"tax_id": " 29 abcde 1234 f1z w "})
        self.assertEqual(duplicate.status, "REJECTED", duplicate.reason)
        self.assertIn(f"VND-{original.submission_id:06d}", duplicate.reason)
        self.assertEqual(db.get_submission(original.submission_id)["status"], "PENDING")
        corrected = self.submit(docs={}, submission_id=original.submission_id, expected_revision=1)
        self.assertEqual(corrected.status, "APPROVED", corrected.reason)
        self.assertEqual(corrected.submission_id, original.submission_id)

    def test_invalid_format_rejection_can_be_corrected_with_same_id(self):
        first = self.submit(data=DATA | {"email": "invalid-address", "ifsc_code": "BAD", "bank_account_number": "123"})
        self.assertEqual(first.status, "REJECTED")
        corrected = self.submit(docs={}, submission_id=first.submission_id, expected_revision=1)
        self.assertEqual(corrected.status, "APPROVED", corrected.reason)
        self.assertEqual(corrected.submission_id, first.submission_id)
        self.assertEqual(corrected.revision, 2)

    def test_screenshot_requirements_are_returned_to_the_application(self):
        self.ai.side_effect = lambda kind, *a, **k: (extraction(kind) | {"document_type": "OTHER", "document_subtype": "GSTIN_SCREENSHOT"}
                                                   if kind == "GST_CERTIFICATE" else extraction(kind), None)
        result = self.submit()
        self.assertEqual(result.status, "PENDING")
        self.assertIn("GSTIN screenshot", result.reason)
        self.assertIn("Form GST REG-06", result.reason)
        self.assertIn("then resubmit", result.reason)
        self.assertEqual(db.get_submission(result.submission_id)["decision_reason"], result.reason)


if __name__ == "__main__":
    unittest.main()
