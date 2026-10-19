"""Streamlit smoke, access, correction and navigation regressions."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from streamlit.proto.WidgetStates_pb2 import WidgetState, WidgetStates

import database as db
from tests.test_workflow import DATA, Upload, extraction


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.paths = patch.multiple(db, DB_PATH=root / "database/test.db", UPLOAD_DIR=root / "uploads", DATA_DIR=root)
        self.paths.start(); self.addCleanup(self.paths.stop)
        self.environment = patch.dict(os.environ, {"VENDENCE_PUBLIC": "0", "VENDENCE_APPROVAL_POLICY": "strict",
                                                 "GEMINI_API_KEY": "synthetic-test-key"}, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        db.initialize_database()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))

    def run_app(self):
        self.app.run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        return self.app

    def nav(self, page):
        self.app.sidebar.button(key="nav_" + page).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.error), 0)

    def fill_new_form(self, **changes):
        values = DATA | {"bank_name": "HDFC Bank"} | changes
        for key in ("vendor_name", "email", "tax_id", "bank_account_holder", "bank_account_number", "ifsc_code"):
            self.app.text_input(key=f"onboard_new_1_{key}").set_value(values[key])
        self.app.selectbox(key="onboard_new_1_bank_name").select(values["bank_name"])

    def save_required_documents(self, sid):
        for kind in ("GST_CERTIFICATE", "BANK_PROOF"):
            upload = Upload(kind)
            doc = db.save_document(sid, kind, upload.name, upload.getvalue(), "image/png")
            db.save_extraction(doc, extraction(kind))

    def submit_with_documents(self, extractor=None):
        extractor = extractor or (lambda kind, *a, **kw: (extraction(kind, **({"bank_name": "HDFC Bank"} if kind == "BANK_PROOF" else {})), None))
        with patch("streamlit.file_uploader", side_effect=lambda label, **kwargs: Upload(label)), \
             patch("workflow.extract_document", side_effect=extractor):
            next(b for b in self.app.button if b.label.startswith("Submit and verify")).click().run(timeout=20)

    def test_four_sections_and_existing_theme(self):
        self.run_app()
        for page in ("New Onboarding", "Verification Center", "Vendor Registry", "Overview"):
            self.nav(page)
        self.assertEqual(len(self.app.sidebar.button), 4)
        source = Path("ui.py").read_text()
        self.assertIn("#F8EBFC", source)
        self.assertIn("#663A91", source)
        self.assertNotIn('section("Verification approach"', source)
        self.assertNotIn("The AI-identified document category differs", source)
        self.assertNotIn('st.expander("Email Communication")', source)

    def test_internal_qa_copy_is_hidden_but_injected_failure_remains_labeled(self):
        os.environ.update(VENDENCE_APPROVAL_POLICY="demo_consistency", VENDENCE_QA_MODE="BROWSER QA — SYNTHETIC INPUTS")
        self.run_app()
        captions = " ".join(item.value for item in self.app.sidebar.caption)
        self.assertIn("Sample workspace", captions)
        self.assertNotIn("BROWSER QA", captions)
        self.assertNotIn("Approval policy:", captions)
        os.environ["VENDENCE_QA_MODE"] = "CONTROLLED GEMINI FAILURE"
        self.run_app()
        self.assertTrue(any("Test mode:" in item.value and "deliberately unavailable" in item.value
                            for item in self.app.sidebar.warning))

    def test_unconfigured_reviewer_setup_is_not_shown_in_vendor_view(self):
        import config
        original_setting = config.setting
        def setting(name, *args, **kwargs):
            return "" if name == "VENDENCE_REVIEWER_PASSWORD" else original_setting(name, *args, **kwargs)
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Documents are required.")
        with patch("config.setting", side_effect=setting):
            self.run_app(); self.nav("Verification Center")
        self.assertFalse(any(item.label == "Reviewer access" for item in self.app.expander))
        self.assertFalse(any("VENDENCE_REVIEWER_PASSWORD" in item.value for item in self.app.info))

    def test_result_popup_shows_status_reason_checks_and_navigation(self):
        for status in ("PENDING", "REJECTED", "APPROVED"):
            with self.subTest(status=status):
                app = AppTest.from_string(f'''import ui
ui.submission_status_dialog(12, {status!r}, "GSTIN structure is invalid.", [{{"code":"GSTIN_FORMAT","outcome":{status!r},"message":"GSTIN structure is invalid."}}])
''').run()
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(app.get("dialog"))
                self.assertTrue(any("VND-000012" in c.value for c in app.caption))
                self.assertTrue(any("GSTIN structure is invalid" in x.value for x in app.markdown))
                self.assertEqual(app.dataframe[0].value.iloc[0]["Verification Check"], "GSTIN Format")
                self.assertTrue(any(b.label == "View application" for b in app.button))

    def test_public_missing_security_configuration_hides_workspace(self):
        os.environ["VENDENCE_PUBLIC"] = "1"
        self.run_app()
        self.assertEqual(len(self.app.sidebar.button), 0)
        self.assertTrue(any("Public startup" in e.value for e in self.app.error))

    def test_public_same_password_is_not_accepted(self):
        os.environ.update(VENDENCE_PUBLIC="1", VENDENCE_ACCESS_PASSWORD="TestPassword123!",
                          VENDENCE_REVIEWER_PASSWORD="TestPassword123!", VENDENCE_DATA_DIR=str(db.DATA_DIR))
        self.run_app()
        self.assertEqual(len(self.app.sidebar.button), 0)

    def test_workspace_password_and_separate_reviewer_gate(self):
        os.environ.update(VENDENCE_ACCESS_PASSWORD="TestAccess123!", VENDENCE_REVIEWER_PASSWORD="TestReview123!")
        self.run_app()
        self.assertEqual(len(self.app.sidebar.button), 0)
        self.app.text_input[0].set_value("incorrect")
        self.app.button[0].click().run()
        self.assertTrue(any("did not match" in e.value for e in self.app.error))
        self.app.text_input[0].set_value("TestAccess123!")
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.sidebar.button), 5)
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Test correction required.")
        self.nav("Verification Center")
        self.assertTrue(any(x.label == "Reviewer Password" for x in self.app.text_input))
        self.assertFalse(any(x.label == "Record Verification Review" for x in self.app.button))

    def test_pending_correction_form_prefills_and_preserves_id(self):
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Synthetic test: incomplete evidence.")
        self.save_required_documents(sid)
        self.run_app(); self.nav("Verification Center")
        self.assertEqual(self.app.text_input(key=f"onboard_correction_{sid}_1_vendor_name").value, DATA["vendor_name"])
        self.assertEqual(self.app.selectbox(key=f"onboard_correction_{sid}_1_bank_name").value, DATA["bank_name"])
        self.app.text_input(key=f"onboard_correction_{sid}_1_email").set_value("corrected@example.test")
        with patch("socket.socket.connect", side_effect=AssertionError("Unexpected network access")):
            next(x for x in self.app.button if x.label.startswith("Resubmit and verify")).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(db.get_submission(sid)["current_revision"], 2)
        self.assertEqual(db.get_submission(sid)["email"], "corrected@example.test")
        self.assertEqual(db.get_submission(sid)["status"], "PENDING")
        self.assertTrue(self.app.get("dialog"))
        next(x for x in self.app.button if x.label == "View application").click().run(timeout=20)
        self.assertEqual(self.app.session_state["nav_page"], "Verification Center")
        self.assertEqual(len(self.app.error), 0)

    def test_searchable_bank_selection_is_saved_in_submission(self):
        self.run_app(); self.nav("New Onboarding")
        bank = self.app.selectbox(key="onboard_new_1_bank_name")
        self.assertIsNone(bank.value)
        self.assertTrue(bank.proto.accept_new_options)
        bank.select("HDFC Bank")
        self.fill_new_form()
        self.submit_with_documents()
        self.assertEqual(len(self.app.exception), 0)
        sid = db.get_submissions()[0]["submission_id"]
        self.assertEqual(db.get_submission(sid)["bank_name"], "HDFC Bank")

    def test_direct_submission_records_operator_policy_without_vendor_checkbox(self):
        from workflow import process_application
        for policy, declared, expected in (("strict", "1", False),
                                           ("demo_consistency", "0", False),
                                           ("demo_consistency", "1", True)):
            with self.subTest(policy=policy, declared=declared):
                os.environ.update(VENDENCE_APPROVAL_POLICY=policy, VENDENCE_SYNTHETIC_DATA_ONLY=declared)
                self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
                self.run_app(); self.nav("New Onboarding")
                self.assertEqual(len(self.app.checkbox), 0)
                self.assertFalse(any("Synthetic demonstration policy:" in x.value for x in self.app.info))
                self.assertFalse(any("Submitting saves" in x.value or "Strict policy requires" in x.value
                                     or "educational GSTIN diagram" in x.value for x in self.app.caption))
                # A stale vendor-session value cannot bypass operator configuration.
                self.app.session_state["synthetic_declared"] = True
                self.fill_new_form(tax_id="INVALID")
                with patch("workflow.process_application", wraps=process_application) as process:
                    self.submit_with_documents()
                self.assertEqual(len(self.app.exception), 0)
                self.assertEqual(process.call_args.kwargs["synthetic_declared"], expected)
                self.assertTrue(self.app.get("dialog"))
                sid = db.get_submissions()[0]["submission_id"]
                self.assertEqual(db.get_submission(sid)["status"], "REJECTED")  # Complete form with an invalid GSTIN is rejected.
                if policy == "demo_consistency":
                    check = next(c for c in db.get_checks(sid) if c["code"] == "SYNTHETIC_DATA_DECLARED")
                    self.assertEqual(check["outcome"], "PASS" if expected else "PENDING")

    def test_direct_correction_uses_workspace_declaration_and_keeps_application_id(self):
        from workflow import process_application
        os.environ.update(VENDENCE_APPROVAL_POLICY="demo_consistency", VENDENCE_SYNTHETIC_DATA_ONLY="1")
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Documents are required.")
        self.save_required_documents(sid)
        self.run_app(); self.nav("Verification Center")
        self.assertFalse(any("synthetic demonstration data" in checkbox.label for checkbox in self.app.checkbox))
        with patch("workflow.process_application", wraps=process_application) as process:
            next(b for b in self.app.button if b.label.startswith("Resubmit and verify")).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(process.call_args.kwargs["synthetic_declared"])
        self.assertEqual(db.get_submission(sid)["current_revision"], 2)
        self.assertEqual(len(db.get_submissions()), 1)
        self.assertTrue(self.app.get("dialog"))

    def test_unlisted_existing_bank_is_preserved_on_correction(self):
        name = "Unlisted Synthetic Credit Bank"
        sid = db.create_vendor_submission(**(DATA | {"bank_name": name}))
        db.update_status(sid, "PENDING", "Synthetic correction.")
        self.save_required_documents(sid)
        self.run_app(); self.nav("Verification Center")
        self.assertEqual(self.app.selectbox(key=f"onboard_correction_{sid}_1_bank_name").value, name)
        next(b for b in self.app.button if b.label.startswith("Resubmit and verify")).click().run(timeout=20)
        self.assertEqual(db.get_submission(sid)["bank_name"], name)

    def test_unselected_bank_remains_missing(self):
        self.run_app(); self.nav("New Onboarding")
        next(b for b in self.app.button if b.label.startswith("Submit and verify")).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(db.get_submissions()), 0)
        self.assertTrue(any("Bank name" in error.value for error in self.app.error))
        self.assertFalse(self.app.get("dialog"))

    def test_gstin_only_form_stays_open_without_saving_or_processing(self):
        self.run_app(); self.nav("New Onboarding")
        self.app.text_input(key="onboard_new_1_tax_id").set_value("INVALID")
        with patch("workflow.process_application") as process, patch("workflow.extract_document") as ai:
            next(b for b in self.app.button if b.label.startswith("Submit and verify")).click().run(timeout=20)
        process.assert_not_called(); ai.assert_not_called()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(db.get_submissions()), 0)
        self.assertFalse(self.app.get("dialog"))
        errors = " ".join(item.value for item in self.app.error)
        self.assertEqual(errors.count("Complete the required fields:"), 1)
        for label in ("Legal company name", "Business email", "Bank name", "Bank account holder", "Bank account number", "IFSC code"):
            self.assertIn(label, errors)
        self.assertIn("GST registration certificate", errors)
        self.assertIn("Bank account proof", errors)
        self.assertEqual(self.app.text_input(key="onboard_new_1_tax_id").value, "INVALID")

    def test_missing_uploads_block_complete_fields_before_saving(self):
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form()
        with patch("workflow.process_application") as process:
            next(b for b in self.app.button if b.label.startswith("Submit and verify")).click().run(timeout=20)
        process.assert_not_called()
        self.assertEqual(len(db.get_submissions()), 0)
        self.assertEqual(len(self.app.error), 1)
        self.assertIn("Upload the required documents:", self.app.error[0].value)

    def test_incomplete_correction_does_not_create_revision_or_events(self):
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Correction requested.")
        self.save_required_documents(sid)
        before_events = db.get_events(sid)
        self.run_app(); self.nav("Verification Center")
        self.app.text_input(key=f"onboard_correction_{sid}_1_email").set_value("   ")
        with patch("workflow.process_application") as process:
            next(b for b in self.app.button if b.label.startswith("Resubmit and verify")).click().run(timeout=20)
        process.assert_not_called()
        self.assertEqual(db.get_submission(sid)["current_revision"], 1)
        self.assertEqual(db.get_submission(sid)["email"], DATA["email"])
        self.assertEqual(db.get_events(sid), before_events)
        self.assertEqual(len(self.app.error), 1)
        self.assertIn("Business email", self.app.error[0].value)

    def test_complete_form_and_documents_process_and_show_decision(self):
        os.environ.update(VENDENCE_APPROVAL_POLICY="demo_consistency", VENDENCE_SYNTHETIC_DATA_ONLY="1")
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form()
        self.submit_with_documents()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.error), 0)
        self.assertEqual(db.get_submissions()[0]["status"], "APPROVED")
        self.assertTrue(self.app.get("dialog"))

    def test_bank_holder_rejection_result_can_be_corrected_under_same_id(self):
        os.environ.update(VENDENCE_APPROVAL_POLICY="demo_consistency", VENDENCE_SYNTHETIC_DATA_ONLY="1")
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form(bank_account_holder="Different Synthetic Person")
        self.submit_with_documents()
        sid = db.get_submissions()[0]["submission_id"]
        self.assertEqual(db.get_submission(sid)["status"], "REJECTED")
        self.assertTrue(self.app.get("dialog"))
        self.assertTrue(any("Correct the name or upload matching bank proof" in item.value for item in self.app.markdown))
        next(b for b in self.app.button if b.label.startswith("Open verification center")).click().run(timeout=20)
        self.app.text_input(key=f"onboard_correction_{sid}_1_bank_account_holder").set_value(DATA["bank_account_holder"])
        with patch("workflow.extract_document", side_effect=AssertionError("Saved extraction should be reused")):
            next(b for b in self.app.button if b.label.startswith("Resubmit and verify")).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(db.get_submissions()), 1)
        self.assertEqual(db.get_submission(sid)["status"], "APPROVED")
        self.assertEqual(db.get_submission(sid)["current_revision"], 2)
        self.assertTrue(any(e["stage"] == "FINAL_DECISION" and e["outcome"] == "REJECTED" for e in db.get_events(sid)))

    def assert_submitted_form_cannot_create_another_application(self, expected_status, **changes):
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form(**changes)
        stale_submit = next(b for b in self.app.button if b.label.startswith("Submit and verify"))
        self.submit_with_documents()
        sid = db.get_submissions()[0]["submission_id"]
        self.assertEqual(db.get_submission(sid)["status"], expected_status)
        self.assertFalse(any(b.label.startswith("Submit and verify") for b in self.app.button))
        baseline = (len(db.get_submissions()), len(db.get_events(sid)), len(db.get_documents(sid)))
        with patch("workflow.extract_document", side_effect=AssertionError("Repeated submit must not process again")):
            # Deliver a delayed event from the removed form, without trying to
            # serialize the old form's widgets after Streamlit discarded them.
            self.app._run(widget_state=WidgetStates(widgets=[
                WidgetState(id=stale_submit.id, trigger_value=True)]), timeout=20)
            self.nav("Overview"); self.nav("New Onboarding")
            self.run_app()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(baseline, (len(db.get_submissions()), len(db.get_events(sid)), len(db.get_documents(sid))))
        self.assertTrue(any(b.label == "Start another application" for b in self.app.button))
        self.assertFalse(any(b.label.startswith("Submit and verify") for b in self.app.button))

    def test_approved_submission_consumes_form_until_explicit_new_application(self):
        os.environ.update(VENDENCE_APPROVAL_POLICY="demo_consistency", VENDENCE_SYNTHETIC_DATA_ONLY="1")
        self.assert_submitted_form_cannot_create_another_application("APPROVED")

    def test_pending_submission_consumes_form_until_explicit_new_application(self):
        self.assert_submitted_form_cannot_create_another_application("PENDING")

    def test_rejected_submission_consumes_form_until_explicit_new_application(self):
        self.assert_submitted_form_cannot_create_another_application("REJECTED", tax_id="INVALID")

    def test_human_labels_are_not_repeated_when_formatting_messages(self):
        import ui
        raw = "Missing mandatory field: Business email. IFSC code is missing. Correct email and ifsc_code."
        text = ui.pretty_message(raw)
        self.assertNotIn("Business Business", text)
        self.assertNotIn("Code code", text)
        self.assertEqual(ui.pretty_message(text), text)

    def test_saved_infographic_reason_uses_simple_display_without_changing_history(self):
        import ui
        old = "GST certificate upload contains an educational GSTIN infographic, not registration evidence. Replace it in VENDENCE with a clear, complete GST registration certificate (Form GST REG-06), then resubmit."
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", old)
        self.run_app(); self.nav("Verification Center")
        shown = " ".join(item.value for item in self.app.markdown)
        self.assertIn("The uploaded GST certificate is invalid.", shown)
        self.assertNotIn("educational GSTIN infographic", shown)
        self.assertIn("Form GST REG-06", shown)
        self.assertEqual(db.get_submission(sid)["decision_reason"], old)

    def test_concise_approval_keeps_policy_in_audit_and_authenticity_details(self):
        import ui
        from workflow import process_application
        reason = ("All configured synthetic demonstration consistency checks passed. "
                  "Document authenticity remains NOT_VERIFIED unless separately recorded; "
                  "no independent government or banking verification is claimed.")
        with patch("workflow.extract_document", side_effect=lambda kind, *a, **kw: (extraction(kind), None)):
            result = process_application(DATA, {kind: Upload(kind) for kind in ("GST_CERTIFICATE", "BANK_PROOF")},
                                         policy="demo_consistency", synthetic_declared=True)
        self.assertEqual(result.status, "APPROVED")
        sid = result.submission_id
        self.run_app(); self.nav("Verification Center")
        shown = " ".join(item.value for item in self.app.markdown)
        self.assertIn("All required information and document consistency checks passed.", shown)
        self.assertIn("Document Authenticity: Not Verified", shown)
        self.assertEqual(db.get_submission(sid)["decision_reason"], reason)
        self.assertTrue(any(event["details"] == reason for event in db.get_events(sid)))
        self.assertIn("no independent government", ui.pretty_message(reason))
        # An extra warning must not be swallowed by the short summary.
        warning = reason + " Additional review required."
        self.assertIn("Additional review required.", ui.decision_message(warning))

    def test_database_write_failure_shows_error_without_application_or_success_dialog(self):
        import sqlite3
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form()
        with patch("workflow.db.create_vendor_submission", side_effect=sqlite3.OperationalError("Controlled write failure")):
            self.submit_with_documents()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(db.get_submissions()), 0)
        self.assertFalse(self.app.get("dialog"))
        self.assertTrue(any("could not be saved" in item.value for item in self.app.error))
        self.assertTrue(any(b.label.startswith("Submit and verify") for b in self.app.button))
        self.submit_with_documents()
        self.assertEqual(len(db.get_submissions()), 1)
        self.assertTrue(self.app.get("dialog"))
        self.assertFalse(any(b.label.startswith("Submit and verify") for b in self.app.button))

    def test_ai_outage_shows_pending_dialog_and_records_failed_checks(self):
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form()
        self.submit_with_documents(extractor=lambda *a, **kw: (None, "Controlled test: Gemini unavailable."))
        self.assertEqual(len(self.app.exception), 0)
        sid = db.get_submissions()[0]["submission_id"]
        self.assertEqual(db.get_submission(sid)["status"], "PENDING")
        self.assertTrue(self.app.get("dialog"))
        self.assertEqual(sum(check["outcome"] == "ERROR" for check in db.get_checks(sid)), 2)
        self.assertTrue(any(event["stage"] == "FINAL_DECISION" and event["outcome"] == "PENDING" for event in db.get_events(sid)))

    def test_invalid_ai_response_is_persisted_pending_and_not_shown_as_success(self):
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form()
        self.submit_with_documents(extractor=lambda *a, **kw: ({}, None))
        self.assertEqual(len(self.app.exception), 0)
        sid = db.get_submissions()[0]["submission_id"]
        self.assertEqual(db.get_submission(sid)["status"], "PENDING")
        self.assertTrue(self.app.get("dialog"))
        self.assertTrue(any(event["stage"] == "PROCESSING_ERROR" for event in db.get_events(sid)))

    def test_document_preview_extraction_and_authenticity_visible(self):
        sid = db.create_vendor_submission(**DATA)
        upload = Upload()
        doc = db.save_document(sid, "GST_CERTIFICATE", upload.name, upload.getvalue(), "image/png")
        db.save_extraction(doc, extraction("GST_CERTIFICATE"))
        self.run_app(); self.nav("Verification Center")
        self.assertTrue(any("Document Authenticity: Not Verified" in x.value for x in self.app.markdown))
        self.assertTrue(any("Registered Legal Name" in frame.value.to_string() for frame in self.app.dataframe))
        self.assertFalse(any(DATA["bank_account_number"] in frame.value.to_string() for frame in self.app.dataframe))

    def test_wrong_document_keeps_actionable_checks_without_technical_banner(self):
        sid = db.create_vendor_submission(**DATA)
        upload = Upload()
        doc = db.save_document(sid, "GST_CERTIFICATE", upload.name, upload.getvalue(), "image/png")
        db.save_extraction(doc, extraction("GST_CERTIFICATE") | {"document_type": "OTHER", "document_subtype": "GSTIN_INFOGRAPHIC"})
        reason = "Replace the GST upload with a registration certificate and resubmit."
        db.save_check(sid, 1, {"code": "GST_CERTIFICATE_IDENTITY", "outcome": "PENDING", "message": reason})
        db.update_status(sid, "PENDING", reason)
        self.run_app(); self.nav("Verification Center")
        self.assertFalse(any("differs from the upload category" in x.value for x in self.app.warning))
        self.assertTrue(any(reason in frame.value.to_string() for frame in self.app.dataframe))
        self.assertFalse(any(x.label == "Email Communication" for x in self.app.expander))

    def test_registry_search_and_status_filter(self):
        sid = db.create_vendor_submission(**DATA)
        db.update_status(sid, "PENDING", "Pending synthetic test.")
        self.run_app(); self.nav("Vendor Registry")
        next(x for x in self.app.selectbox if x.label == "Status").select("Pending").run()
        self.assertTrue(any(DATA["vendor_name"] in frame.value.to_string() for frame in self.app.dataframe))
        next(x for x in self.app.text_input if x.label == "Search").set_value("no-such-vendor").run()
        self.assertTrue(any("No applications match these filters" in x.value for x in self.app.info))

    def test_filtered_selection_sends_updated_id_to_the_browser_widget(self):
        app = AppTest.from_string('''import streamlit as st
import ui
if st.button("Filter to first application"):
    st.session_state.filtered = True
records = [{"submission_id": 1}] if st.session_state.get("filtered") else [{"submission_id": 1}, {"submission_id": 2}]
ui.choose_application(records, "registry_selected")
''').run()
        app.selectbox[0].set_value(2).run()
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox[0].value, 1)
        self.assertTrue(app.selectbox[0].proto.set_value)

    def test_original_pdf_component_available(self):
        from pypdf import PdfWriter
        from io import BytesIO
        writer = PdfWriter(); writer.add_blank_page(width=400, height=600)
        buffer = BytesIO(); writer.write(buffer)
        sid = db.create_vendor_submission(**DATA)
        db.save_document(sid, "GST_CERTIFICATE", "synthetic.pdf", buffer.getvalue(), "application/pdf")
        self.run_app(); self.nav("Verification Center")
        self.assertFalse(any("install" in item.value.lower() and "pdf" in item.value.lower() for item in self.app.warning))

    def test_open_result_replaces_previous_verification_selection(self):
        app = AppTest.from_string('''import ui
ui.choose_application([{"submission_id":1},{"submission_id":2}], "verify_selected")
ui.processing_result(2, "PENDING", "Synthetic second application.", [])
''').run()
        self.assertEqual(app.selectbox[0].value, 1)
        next(b for b in app.button if b.label.startswith("Open verification center")).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox[0].value, 2)

    def test_ai_explanations_cannot_expose_full_account_in_tables(self):
        app = AppTest.from_string('''import ui
ui.extracted_table({"account_number":"001234567890",
                    "classification_evidence":"Account 001234567890 and ACCOUNT001234567890 on confirmation",
                    "document_title":"Account 0012 3456 7890 confirmation"})
''').run()
        text = app.dataframe[0].value.to_string()
        self.assertNotIn("001234567890", text)
        self.assertNotIn("0012 3456 7890", text)
        self.assertIn("7890", text)

    def test_resume_by_application_id_opens_correct_existing_record(self):
        first = db.create_vendor_submission(**DATA)
        second = db.create_vendor_submission(**(DATA | {"vendor_name": "Second Synthetic Vendor"}))
        self.run_app(); self.nav("Verification Center")
        self.app.selectbox(key="verify_selected").set_value(second).run()
        self.nav("New Onboarding")
        next(x for x in self.app.text_input if x.label == "Existing Application ID").set_value(f"vnd-{first:06d}")
        next(b for b in self.app.button if b.label.startswith("Continue application")).click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.selectbox(key="verify_selected").value, first)
        self.assertEqual(self.app.text_input(key=f"onboard_correction_{first}_1_vendor_name").value, DATA["vendor_name"])
        self.assertEqual(len(db.get_submissions()), 2)
        self.assertEqual(db.get_submission(first)["current_revision"], 1)

    def test_resume_unknown_id_is_read_only_and_does_not_open_another_record(self):
        db.create_vendor_submission(**DATA)
        self.run_app(); self.nav("New Onboarding")
        next(x for x in self.app.text_input if x.label == "Existing Application ID").set_value("VND-999999")
        next(b for b in self.app.button if b.label.startswith("Continue application")).click().run(timeout=20)
        self.assertEqual(self.app.session_state["nav_page"], "New Onboarding")
        self.assertTrue(any("No matching application" in x.value for x in self.app.warning))
        self.assertEqual(len(db.get_submissions()), 1)

    def test_start_another_application_clears_fields_without_creating_record(self):
        self.run_app(); self.nav("New Onboarding")
        self.fill_new_form(vendor_name="Previous Synthetic Vendor")
        self.submit_with_documents()
        self.assertEqual(len(db.get_submissions()), 1)
        next(b for b in self.app.button if b.label == "Start another application").click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.text_input(key="onboard_new_2_vendor_name").value, "")
        self.assertEqual(self.app.text_input(key="onboard_new_2_bank_account_number").value, "")
        self.assertEqual(len(db.get_submissions()), 1)

    def test_reviewer_withdrawal_refreshes_decision_and_enables_reprocessing(self):
        from workflow import process_application
        with patch("workflow.extract_document", side_effect=lambda kind, *a, **k: (extraction(kind), None)):
            result = process_application(DATA, {kind: Upload(kind) for kind in ("GST_CERTIFICATE", "BANK_PROOF")},
                                         policy="demo_consistency", synthetic_declared=True)
        self.assertEqual(result.status, "APPROVED")
        os.environ.update(VENDENCE_REVIEWER_PASSWORD="SyntheticReview123!", VENDENCE_APPROVAL_POLICY="demo_consistency")
        self.run_app(); self.nav("Verification Center")
        next(x for x in self.app.text_input if x.label == "Reviewer Password").set_value("SyntheticReview123!")
        next(b for b in self.app.button if b.label == "Unlock").click().run(timeout=20)
        next(x for x in self.app.selectbox if x.label == "Verification State").set_value("VERIFICATION_FAILED")
        next(x for x in self.app.text_input if x.label == "Reviewer Name").set_value("Synthetic Test Reviewer")
        next(x for x in self.app.text_input if x.label == "Independent Evidence Reference").set_value("SIMULATED_UNIT_TEST_ONLY")
        with patch("socket.socket.connect", side_effect=AssertionError("Unexpected network access")):
            next(b for b in self.app.button if b.label == "Record Verification Review").click().run(timeout=20)
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(db.get_submission(result.submission_id)["status"], "PENDING")
        self.assertTrue(any(b.label == "Re-run verification" for b in self.app.button))
        self.assertTrue(any("Review saved" in x.value for x in self.app.success))


if __name__ == "__main__":
    unittest.main()
