"""Repeatable deterministic rule regressions using synthetic data only."""
import io
import unittest
from unittest.mock import patch

from PIL import Image

import validation as v


SYNTHETIC = {
    "vendor_name": "Example Synth Private Limited", "email": "demo@example.test", "country": "India",
    "tax_id": "29ABCDE1234F1ZW", "bank_name": "Synthetic Demonstration Bank",
    "bank_account_holder": "Example Synth Pvt. Ltd.", "bank_account_number": "001234567890",
    "ifsc_code": "DEMO0000001",
}


def checks_by_code(checks):
    return {check["code"]: check for check in checks}


def passed_inventory(policy="strict"):
    return [v.make_check(code, "PASS", "Synthetic configured check passed.")
            for code in sorted(v.required_check_codes(policy))]


def uploaded(content, name="synthetic.pdf"):
    value = io.BytesIO(content)
    value.name = name
    return value


class RequiredAndFormatTests(unittest.TestCase):
    def test_form_completeness_requires_fields_and_current_or_replacement_documents(self):
        fields, docs = v.missing_submission_requirements(SYNTHETIC, {})
        self.assertEqual(fields, [])
        self.assertEqual(len(docs), 2)
        self.assertEqual(v.missing_submission_requirements(SYNTHETIC, {}, {"GST_CERTIFICATE", "BANK_PROOF"}), ([], []))
        self.assertEqual(v.missing_submission_requirements(SYNTHETIC, {"BANK_PROOF": object()}, {"GST_CERTIFICATE"}), ([], []))
        fields, docs = v.missing_submission_requirements(SYNTHETIC | {"email": " \t"}, {}, {"GST_CERTIFICATE", "BANK_PROOF"})
        self.assertEqual(fields, ["Business email"])
        self.assertEqual(docs, [])

    def test_condensed_explanation_cannot_turn_a_blocked_check_into_approval(self):
        checks = [v.make_check("GSTIN_CHECKSUM", "PENDING", "Waiting for a valid GSTIN.")]
        status, reason = v.determine_decision(checks, required_codes={"GSTIN_CHECKSUM"})
        self.assertEqual(status, "PENDING")
        self.assertTrue(reason)

    def test_every_required_field(self):
        self.assertTrue(all(item["outcome"] == "PASS" for item in v.check_required_fields(SYNTHETIC)))
        for field in v.REQUIRED_FIELDS:
            with self.subTest(field=field):
                data = {**SYNTHETIC, field: " \t"}
                self.assertEqual(checks_by_code(v.check_required_fields(data))[f"REQUIRED_{field.upper()}"]["outcome"], "PENDING")

    def test_nonstring_required_values_do_not_pass(self):
        self.assertEqual(v.check_required_fields({"vendor_name": {"unexpected": "data"}})[0]["outcome"], "PENDING")

    def test_happy_formats(self):
        self.assertTrue(all(item["outcome"] == "PASS" for item in v.check_field_formats(SYNTHETIC)))

    def test_gstin_known_vectors_and_typo(self):
        for gstin in ("27AAPFU0939F1ZV", "27AABCU9603R1ZN", SYNTHETIC["tax_id"]):
            with self.subTest(gstin=gstin):
                self.assertTrue(v.valid_gstin_checksum(gstin))
                self.assertFalse(v.valid_gstin_checksum(gstin[:-1] + ("0" if gstin[-1] != "0" else "1")))

    def test_gstin_normalization_is_whitespace_and_case_only(self):
        self.assertEqual(v.normalize_code(" 29abcde 1234f1z\tw "), SYNTHETIC["tax_id"])
        self.assertNotEqual(v.normalize_code("29ABCDE1234F1Z-W"), SYNTHETIC["tax_id"])
        self.assertNotEqual(v.normalize_code("29ABCDE1234F1ZX"), SYNTHETIC["tax_id"])

    def test_gstin_state_and_structure(self):
        for state in ("00", "25", "28", "39", "96"):
            data = {**SYNTHETIC, "tax_id": state + SYNTHETIC["tax_id"][2:]}
            self.assertEqual(checks_by_code(v.check_field_formats(data))["GSTIN_STATE_CODE"]["outcome"], "REJECTED")
        for state in ("01", "26", "38", "97", "99"):
            prefix = state + SYNTHETIC["tax_id"][2:14]
            data = {**SYNTHETIC, "tax_id": prefix + v.gstin_check_digit(prefix)}
            self.assertEqual(checks_by_code(v.check_field_formats(data))["GSTIN_STATE_CODE"]["outcome"], "PASS")
        invalid = {**SYNTHETIC, "tax_id": "29ABCDE1234F0ZW"}
        self.assertEqual(checks_by_code(v.check_field_formats(invalid))["GSTIN_FORMAT"]["outcome"], "REJECTED")

    def test_invalid_provided_gstin_is_rejected_but_missing_stays_pending(self):
        for value, code in (("INVALID-GSTIN", "GSTIN_FORMAT"),
                            ("29ABCDE1234F1Z0", "GSTIN_CHECKSUM"),
                            ("00ABCDE1234F1Z0", "GSTIN_STATE_CODE")):
            with self.subTest(value=value):
                checks = checks_by_code(v.check_field_formats(SYNTHETIC | {"tax_id": value}))
                self.assertEqual(checks[code]["outcome"], "REJECTED")
        for value in ("", " \t\n"):
            checks = v.check_field_formats(SYNTHETIC | {"tax_id": value})
            self.assertFalse(any(c["outcome"] == "REJECTED" for c in checks))

    def test_checksum_invalid_inputs(self):
        for value in (None, 123, "", "abc", "29ABCDE1234F1Z-", "29ABCDE1234F1Z🙂"):
            self.assertFalse(v.valid_gstin_checksum(value))
        with self.assertRaises(ValueError):
            v.gstin_check_digit("short")

    def test_missing_formats_are_explicit(self):
        checks = checks_by_code(v.check_field_formats({}))
        self.assertEqual(len(checks), 8)
        self.assertTrue(all(check["outcome"] == "PENDING" for check in checks.values()))

    def test_email_scope_ifsc_and_account(self):
        for email in ("example.test", "a@@b.test", "a b@example.test", "a@example.",
                      ".a@example.test", "a.@example.test", "a..b@example.test", "a@ex..test", "a@-example.test", "a" * 65 + "@example.test"):
            self.assertEqual(checks_by_code(v.check_field_formats({**SYNTHETIC, "email": email}))["EMAIL_FORMAT"]["outcome"], "REJECTED")
        for ifsc in ("DEMO1000001", "DEM0000001", "DEMO00000012", "DEM00000001", "DEMO0!!!!!!"):
            self.assertEqual(checks_by_code(v.check_field_formats({**SYNTHETIC, "ifsc_code": ifsc}))["IFSC_FORMAT"]["outcome"], "REJECTED")
        for account in ("12345678", "1234567890123456789", "********1234", "１２３４５６７８９", "abc123456789"):
            self.assertEqual(checks_by_code(v.check_field_formats({**SYNTHETIC, "bank_account_number": account}))["ACCOUNT_NUMBER_FORMAT"]["outcome"], "REJECTED")
        formatted = {**SYNTHETIC, "ifsc_code": " demo 0000001 ", "bank_account_number": "0012-3456 7890"}
        self.assertTrue(all(check["outcome"] == "PASS" for check in v.check_field_formats(formatted)))
        self.assertEqual(checks_by_code(v.check_field_formats({**SYNTHETIC, "country": "UK"}))["COUNTRY_SCOPE"]["outcome"], "PENDING")


class EvidenceAndDuplicateTests(unittest.TestCase):
    def test_clear_holder_contradiction_is_rejected_with_correction_message(self):
        evidence = {"document_type": "BANK_PROOF", "document_subtype": "BANK_ACCOUNT_CONFIRMATION",
                    "account_holder": "Different Synthetic Person"}
        checks = checks_by_code(v.check_document_evidence("BANK_PROOF", SYNTHETIC, evidence))
        check = checks["BANK_PROOF_BANK_ACCOUNT_HOLDER_MATCH"]
        self.assertEqual(check["outcome"], "REJECTED")
        self.assertEqual(check["message"], "The account holder name does not match the uploaded bank document. Correct the name or upload matching bank proof, then resubmit.")

    def test_ambiguous_or_missing_holder_evidence_stays_pending(self):
        for holder in ("", "???", "****", "Unknown", "Not available", "Example Synth",
                       "E Synth Private Limited", "Example Synht Private Limited", "ExampleSynth"):
            with self.subTest(holder=holder):
                evidence = {"document_type": "BANK_PROOF", "document_subtype": "BANK_STATEMENT",
                            "account_holder": holder}
                check = checks_by_code(v.check_document_evidence("BANK_PROOF", SYNTHETIC, evidence))["BANK_PROOF_BANK_ACCOUNT_HOLDER_MATCH"]
                self.assertEqual(check["outcome"], "PENDING")

    def test_bank_name_normalization_does_not_merge_different_banks(self):
        self.assertTrue(v.same_value("HDFC Bank", "HDFC BANK LTD.", "bank"))
        self.assertTrue(v.same_value("ICICI Bank Limited", "icici bank", "bank"))
        self.assertFalse(v.same_value("IDBI Bank", "IDFC FIRST Bank", "bank"))
        self.assertFalse(v.same_value("HDFC Bank", "HDFC Securities", "bank"))
        self.assertFalse(v.same_value("", "", "bank"))
        self.assertFalse(v.same_value("Example Services", "Example Services Limited", "name"))
    def test_conservative_name_matching(self):
        self.assertTrue(v.same_value("Example Synth Pvt. Ltd.", "EXAMPLE SYNTH PRIVATE LIMITED", "name"))
        self.assertTrue(v.same_value("A & B Ltd.", "A and B Limited", "name"))
        self.assertFalse(v.same_value("Example Synth", "Example Synth Private Limited", "name"))
        self.assertFalse(v.same_value("", "", "name"))
        self.assertFalse(v.same_value("---", "...", "name"))
        self.assertFalse(v.same_value("00123456789", "123456789", "account"))

    def test_wrong_document_and_bank_subtype(self):
        for subtype in ("GSTIN_INFOGRAPHIC", "GSTIN_SCREENSHOT", "UNREADABLE", "OTHER"):
            checks = v.check_document_evidence("GST_CERTIFICATE", SYNTHETIC, {"document_type": "OTHER", "document_subtype": subtype})
            self.assertEqual(checks[0]["outcome"], "PENDING")
        bank = {"document_type": "BANK_PROOF", "document_subtype": "GSTIN_SCREENSHOT"}
        self.assertEqual(v.check_document_evidence("BANK_PROOF", SYNTHETIC, bank)[0]["outcome"], "PENDING")

    def test_gst_legal_name_never_falls_back_to_trade_name(self):
        evidence = {"document_type": "GST_CERTIFICATE", "legal_name": "Different Proprietor",
                    "trade_name": SYNTHETIC["vendor_name"], "gstin": SYNTHETIC["tax_id"]}
        checks = checks_by_code(v.check_document_evidence("GST_CERTIFICATE", SYNTHETIC, evidence))
        self.assertEqual(checks["GST_CERTIFICATE_VENDOR_NAME_MATCH"]["outcome"], "PENDING")
        self.assertEqual(checks["GST_CERTIFICATE_TAX_ID_MATCH"]["outcome"], "PASS")
        evidence["legal_name"] = ""
        self.assertEqual(v.check_document_evidence("GST_CERTIFICATE", SYNTHETIC, evidence)[1]["outcome"], "PENDING")

    def test_wrong_document_requirements_name_the_upload_and_replacement(self):
        for subtype, description in (("GSTIN_INFOGRAPHIC", "infographic"),
                                     ("GSTIN_SCREENSHOT", "GSTIN screenshot"),
                                     ("UNREADABLE", "blank or unreadable")):
            with self.subTest(subtype=subtype):
                check = v.check_document_evidence("GST_CERTIFICATE", SYNTHETIC,
                    {"document_type": "OTHER", "document_subtype": subtype})[0]
                self.assertEqual(check["outcome"], "PENDING")
                if subtype == "GSTIN_INFOGRAPHIC":
                    self.assertIn("The uploaded GST certificate is invalid.", check["message"])
                    self.assertNotIn("infographic", check["message"])
                else:
                    self.assertIn("GST certificate upload", check["message"])
                    self.assertIn(description, check["message"])
                self.assertIn("Form GST REG-06", check["message"])
                self.assertIn("resubmit", check["message"])
        bank = v.check_document_evidence("BANK_PROOF", SYNTHETIC,
                                        {"document_type": "OTHER", "document_subtype": "OTHER"})[0]
        self.assertIn("Bank proof upload", bank["message"])
        self.assertIn("bank statement, account confirmation, or cancelled cheque", bank["message"])

    def test_all_bank_fields_compared_and_masked_accounts_pending(self):
        evidence = {"document_type": "BANK_PROOF", "document_subtype": "BANK_STATEMENT",
                    "account_holder": SYNTHETIC["vendor_name"], "account_number": SYNTHETIC["bank_account_number"],
                    "ifsc": SYNTHETIC["ifsc_code"], "bank_name": SYNTHETIC["bank_name"]}
        self.assertTrue(all(check["outcome"] == "PASS" for check in v.check_document_evidence("BANK_PROOF", SYNTHETIC, evidence)))
        for field in ("account_holder", "account_number", "ifsc", "bank_name"):
            with self.subTest(field=field):
                bad = {**evidence, field: "OTHER1234"}
                self.assertTrue(any(check["outcome"] == "PENDING" for check in v.check_document_evidence("BANK_PROOF", SYNTHETIC, bad)))
        self.assertFalse(v.same_value("001234567890", "********7890", "account"))

    def test_duplicate_outcomes(self):
        self.assertEqual(v.check_duplicate(None)["outcome"], "PASS")
        for status, expected in (("APPROVED", "REJECTED"), ("PENDING", "REJECTED"), ("SUBMITTED", "REJECTED"),
                                 ("PROCESSING", "REJECTED"), ("REJECTED", "PASS"), ("UNKNOWN", "PENDING")):
            self.assertEqual(v.check_duplicate({"submission_id": 1, "status": status})["outcome"], expected)


class DecisionAndAuthenticityTests(unittest.TestCase):
    def test_all_required_pass(self):
        self.assertEqual(v.determine_decision(passed_inventory())[0], "APPROVED")

    def test_empty_partial_and_malformed_never_approve(self):
        for checks in ([], None, {}, [v.make_check("ANY", "PASS", "Some check passed.")],
                       [None], [{"outcome": "PASS"}], ["PASS"]):
            with self.subTest(checks=checks):
                self.assertEqual(v.determine_decision(checks)[0], "PENDING")

    def test_every_nonpass_outcome_blocks_approval(self):
        for outcome in ("FAIL", "ERROR", "PENDING", "UNKNOWN", "SUCCESS", "pass", None, ""):
            with self.subTest(outcome=outcome):
                checks = passed_inventory()
                checks[0] = {**checks[0], "outcome": outcome}
                self.assertEqual(v.determine_decision(checks)[0], "PENDING")

    def test_each_missing_required_check_blocks(self):
        complete = passed_inventory()
        for index in range(len(complete)):
            self.assertEqual(v.determine_decision(complete[:index] + complete[index + 1:])[0], "PENDING")

    def test_duplicate_check_code_is_ambiguous(self):
        checks = passed_inventory()
        self.assertEqual(v.determine_decision(checks + [checks[0]])[0], "PENDING")

    def test_rejection_wins_even_with_errors(self):
        checks = passed_inventory() + [v.make_check("EXTRA", "ERROR", "Technical error.")]
        checks[0]["outcome"] = "REJECTED"
        self.assertEqual(v.determine_decision(checks)[0], "REJECTED")

    def test_custom_and_invalid_configuration(self):
        checks = [v.make_check("CUSTOM", "PASS", "Configured check passed.")]
        self.assertEqual(v.determine_decision(checks, required_codes={"CUSTOM"})[0], "APPROVED")
        for configuration in (set(), {None}, 42, [["unhashable"]]):
            self.assertEqual(v.determine_decision(checks, required_codes=configuration)[0], "PENDING")
        self.assertEqual(v.determine_decision(passed_inventory(), policy="typo")[0], "PENDING")

    def test_strict_fabricated_matching_document_is_not_verified(self):
        checks = passed_inventory()
        for index, check in enumerate(checks):
            if check["code"].endswith("_AUTHENTICITY"):
                checks[index] = v.check_authenticity(check["code"].removesuffix("_AUTHENTICITY"))
        status, reason = v.determine_decision(checks)
        self.assertEqual(status, "PENDING")
        self.assertIn("NOT_VERIFIED", reason)

    def test_authorized_verification_requires_evidence_and_reviewer(self):
        record = {"state": "VERIFIED", "method": "GST_PORTAL_AND_ORIGINAL", "reviewer": "Authorized demo reviewer",
                  "evidence_reference": "synthetic test of record interface only"}
        self.assertEqual(v.check_authenticity("GST_CERTIFICATE", record)["outcome"], "PASS")
        for field in ("method", "reviewer", "evidence_reference"):
            bad = {**record, field: ""}
            self.assertEqual(v.check_authenticity("GST_CERTIFICATE", bad)["outcome"], "ERROR")
        self.assertEqual(v.check_authenticity("GST_CERTIFICATE", {**record, "method": "GEMINI_VISUAL"})["outcome"], "ERROR")
        self.assertEqual(v.check_authenticity("BANK_PROOF", {**record, "method": "GST_PORTAL_AND_ORIGINAL"})["outcome"], "ERROR")
        self.assertEqual(v.check_authenticity("GST_CERTIFICATE", {"state": "VERIFICATION_FAILED"})["outcome"], "PENDING")
        self.assertEqual(v.check_authenticity("GST_CERTIFICATE", {"state": "UNKNOWN"})["outcome"], "ERROR")

    def test_demo_exception_is_explicit_and_requires_synthetic_declaration(self):
        check = v.check_authenticity("GST_CERTIFICATE", policy="demo_consistency")
        self.assertEqual(check["outcome"], "PASS")
        self.assertIn("NOT_VERIFIED", check["message"])
        self.assertIn("synthetic", check["message"])
        checks = [check for check in passed_inventory("demo_consistency") if check["code"] not in {"APPROVAL_POLICY", "SYNTHETIC_DATA_DECLARED"}]
        self.assertEqual(v.determine_decision(checks + v.check_approval_policy("demo_consistency"), policy="demo_consistency")[0], "PENDING")
        status, reason = v.determine_decision(checks + v.check_approval_policy("demo_consistency", True), policy="demo_consistency")
        self.assertEqual(status, "APPROVED")
        self.assertIn("NOT_VERIFIED", reason)
        failed = v.check_authenticity("GST_CERTIFICATE", {"state": "VERIFICATION_FAILED"}, "demo_consistency")
        self.assertEqual(failed["outcome"], "PENDING")


class UploadTests(unittest.TestCase):
    def test_missing_empty_unsupported_corrupt_size(self):
        for document in (None, uploaded(b""), uploaded(b"plain text"), uploaded(b"%PDF-invalid"),
                         uploaded(b"\x89PNG\r\n\x1a\nbroken"), uploaded(b"x" * (v.MAX_DOCUMENT_SIZE + 1))):
            parsed, check = v.inspect_document("GST_CERTIFICATE", document)
            self.assertIsNone(parsed)
            self.assertEqual(check["outcome"], "PENDING")

    def test_valid_image_content_not_filename(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
        document, check = v.inspect_document("BANK_PROOF", uploaded(buffer.getvalue(), "incorrect.exe"))
        self.assertEqual(check["outcome"], "PASS")
        self.assertEqual(document["mime_type"], "image/png")

    def test_pixel_limit(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
        with patch.object(v, "MAX_IMAGE_PIXELS", 100):
            self.assertEqual(v.inspect_document("BANK_PROOF", uploaded(buffer.getvalue()))[1]["outcome"], "PENDING")

    def test_corrupt_content_names_the_document_and_requests_a_replacement(self):
        for kind, label in (("GST_CERTIFICATE", "GST registration certificate"), ("BANK_PROOF", "bank account proof")):
            with self.subTest(kind=kind):
                document, check = v.inspect_document(kind, uploaded(b"%PDF-1.7\ninvalid object tree\n"))
                self.assertIsNone(document)
                self.assertEqual(check["outcome"], "PENDING")
                self.assertIn(label, check["message"])
                self.assertIn("Upload a clear, valid PDF or image and resubmit", check["message"])

    def test_pdf_reader_and_encryption(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        plain = io.BytesIO()
        writer.write(plain)
        self.assertEqual(v.inspect_document("GST_CERTIFICATE", uploaded(plain.getvalue()))[1]["outcome"], "PASS")
        with patch.object(v, "MAX_DOCUMENT_PAGES", 0):
            self.assertEqual(v.inspect_document("GST_CERTIFICATE", uploaded(plain.getvalue()))[1]["outcome"], "PENDING")
        writer.encrypt("synthetic-test-password")
        encrypted = io.BytesIO()
        writer.write(encrypted)
        self.assertEqual(v.inspect_document("GST_CERTIFICATE", uploaded(encrypted.getvalue()))[1]["outcome"], "PENDING")


if __name__ == "__main__":
    unittest.main()
