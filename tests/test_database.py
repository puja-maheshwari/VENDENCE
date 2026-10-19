"""Isolated persistence regressions; all data/files are synthetic temporary fixtures."""
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from validation import required_check_codes


DATA = {
    "vendor_name": "Synthetic Lavender Services Private Limited",
    "email": "vendor@example.test",
    "country": "India",
    "tax_id": "27ABCDE1234F1Z5",
    "bank_account_holder": "Synthetic Lavender Services Private Limited",
    "bank_name": "Synthetic Test Bank",
    "bank_account_number": "123456789012",
    "ifsc_code": "TEST0123456",
}


def passed_checks(policy="demo_consistency"):
    return [{"code": code, "outcome": "PASS", "message": "Synthetic fixture passed."}
            for code in sorted(required_check_codes(policy))]


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(db, DB_PATH=self.root / "database" / "test.db",
                                   UPLOAD_DIR=self.root / "uploads")
        self.paths.start()
        db.initialize_database()

    def tearDown(self):
        self.paths.stop()
        self.temp.cleanup()

    def create(self, **changes):
        return db.create_vendor_submission(**(DATA | changes))

    def docs(self, sid):
        return [db.save_document(sid, kind, f"{kind}.pdf", b"%PDF-1.4 synthetic fixture", "application/pdf")
                for kind in ("GST_CERTIFICATE", "BANK_PROOF")]

    def saved_passed_checks(self, sid, policy="demo_consistency"):
        checks = passed_checks(policy)
        for check in checks:
            db.save_check(sid, db.get_submission(sid)["current_revision"], check)
        return checks

    def scalar(self, sql):
        c = db.get_connection()
        try:
            return c.execute(sql).fetchone()[0]
        finally:
            c.close()

    def test_creation_persists_revision_and_event_without_bank_event_data(self):
        sid = self.create()
        self.assertEqual(db.get_submission(sid)["current_revision"], 1)
        self.assertEqual(db.get_submission(sid)["status"], "SUBMITTED")
        self.assertEqual([row["revision"] for row in db.get_revisions(sid)], [1])
        events = db.get_events(sid)
        self.assertEqual(events[0]["stage"], "SUBMISSION_RECEIVED")
        self.assertNotIn(DATA["bank_account_number"], json.dumps(events))
        self.assertNotIn("bank_account_number", db.get_submissions()[0])

    def test_migrations_are_idempotent(self):
        sid = self.create()
        self.docs(sid)
        db.log_event(sid, "SYNTHETIC_EVENT", "SUCCESS", "Synthetic fixture.")
        counts = [self.scalar(f"SELECT COUNT(*) FROM {table}") for table in
                  ("vendor_submissions", "vendor_documents", "processing_events", "submission_revisions")]
        db.initialize_database()
        db.initialize_database()
        self.assertEqual(counts, [self.scalar(f"SELECT COUNT(*) FROM {table}") for table in
                                 ("vendor_submissions", "vendor_documents", "processing_events", "submission_revisions")])
        self.assertEqual(self.scalar("PRAGMA user_version"), 3)

    def test_current_schema_restart_does_not_invent_extractions_for_reused_documents(self):
        sid = self.create()
        documents = self.docs(sid)
        for document_id in documents:
            db.save_extraction(document_id, {"synthetic": "saved extraction"})
        db.revise_submission(sid, DATA, 1, correction_reason="Synthetic correction reuses documents.")
        connection = db.get_connection()
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        before = {table: [tuple(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')] for table in tables}
        connection.close()
        db.initialize_database()
        db.initialize_database()
        connection = db.get_connection()
        after = {table: [tuple(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')] for table in tables}
        connection.close()
        self.assertEqual(after, before)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM document_extractions"), 2)

    def test_legacy_extractions_are_backfilled_once_during_upgrade(self):
        sid = self.create()
        document_id = self.docs(sid)[0]
        db.save_extraction(document_id, {"synthetic": "legacy extraction"})
        connection = db.get_connection()
        with connection:
            connection.execute("DELETE FROM document_extractions")
            connection.execute("PRAGMA user_version = 2")
        connection.close()
        db.initialize_database()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM document_extractions"), 1)
        db.initialize_database()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM document_extractions"), 1)

    def test_new_store_has_no_email_tables_and_legacy_history_is_preserved(self):
        c = db.get_connection()
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='communication_attempts'").fetchone())
        with c:
            c.execute("CREATE TABLE communication_attempts (communication_id INTEGER PRIMARY KEY, status TEXT)")
            c.execute("INSERT INTO communication_attempts VALUES (1,'ACCEPTED')")
        c.close()
        db.initialize_database()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM communication_attempts"), 1)

    def test_correction_audit_summary_masks_numeric_bank_details(self):
        sid = self.create()
        db.revise_submission(sid, DATA, 1, correction_reason="Corrected account " + DATA["bank_account_number"] + " ACCOUNT" + DATA["bank_account_number"])
        summary = db.get_revisions(sid)[-1]["correction_reason"]
        self.assertNotIn(DATA["bank_account_number"], summary)
        self.assertIn("[number hidden]", summary)

    def test_legacy_schema_migrates_preserving_records_and_status_constraint(self):
        legacy_path = self.root / "legacy.db"
        c = sqlite3.connect(legacy_path)
        c.executescript("""
            CREATE TABLE vendor_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_name TEXT NOT NULL,
                email TEXT NOT NULL,country TEXT NOT NULL,tax_id TEXT,bank_account_holder TEXT,
                status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ('SUBMITTED','PROCESSING','APPROVED','PENDING','REJECTED')),
                decision_reason TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE vendor_documents(document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,document_type TEXT NOT NULL,file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE processing_events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,stage TEXT NOT NULL,outcome TEXT NOT NULL,
                details TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO vendor_submissions(vendor_name,email,country,tax_id,status)
                VALUES('Synthetic Legacy','legacy@example.test','India','27 ABCDE1234F1Z5','PENDING');
            INSERT INTO vendor_documents(submission_id,document_type,file_name,file_path)
                VALUES(1,'GST_CERTIFICATE','legacy.pdf','synthetic-legacy.pdf');
            INSERT INTO processing_events(submission_id,stage,outcome,details)
                VALUES(1,'SUBMISSION_RECEIVED','SUCCESS','Synthetic legacy fixture');
        """)
        c.close()
        with patch.object(db, "DB_PATH", legacy_path):
            db.initialize_database()
            db.initialize_database()
            self.assertEqual(db.get_submission(1)["status"], "PENDING")
            self.assertEqual(db.get_submission(1)["normalized_tax_id"], DATA["tax_id"])
            self.assertEqual(len(db.get_documents(1)), 1)
            self.assertEqual(db.get_documents(1)[0]["file_path"], "synthetic-legacy.pdf")
            self.assertEqual(len(db.get_events(1)), 1)
            self.assertEqual(len(db.get_revisions(1)), 1)
            c = db.get_connection()
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    c.execute("UPDATE vendor_submissions SET status='UNSAFE' WHERE submission_id=1")
            finally:
                c.close()

    def test_duplicate_whitespace_normalization_and_distinct_identifiers(self):
        sid = self.create(tax_id=" 27 AB\tCDE1234F1Z5\n")
        self.assertEqual(db.find_duplicate("27abcde1234f1z5", 999)["submission_id"], sid)
        self.assertEqual(db.find_duplicate("27\u00a0ABCDE1234F1Z5", 999)["submission_id"], sid)
        self.assertIsNone(db.find_duplicate("27ABCDE1234F1Z6", 999))
        self.assertIsNone(db.find_duplicate("27-ABCDE1234F1Z5", 999))
        self.assertIsNone(db.find_duplicate(DATA["tax_id"], sid))
        self.assertIsNone(db.find_duplicate("", sid))

    def test_duplicate_priority_approved_then_pending_then_rejected(self):
        rejected = self.create()
        db.update_status(rejected, "REJECTED", "Synthetic rejected fixture.")
        pending = self.create()
        self.assertEqual(db.find_duplicate(DATA["tax_id"], 999)["submission_id"], pending)
        # Simulate the pre-existing legacy APPROVED record, without bypassing production approval APIs.
        c = db.get_connection()
        with c:
            c.execute("UPDATE vendor_submissions SET status='APPROVED' WHERE submission_id=?", (rejected,))
        c.close()
        self.assertEqual(db.find_duplicate(DATA["tax_id"], 999)["submission_id"], rejected)

    def test_documents_return_paths_hashes_and_only_current_category(self):
        sid = self.create()
        first = db.save_document(sid, "GST_CERTIFICATE", "../first.pdf", b"%PDF-1.4 first", "application/pdf")
        second = db.save_document(sid, "GST_CERTIFICATE", "second.pdf", b"%PDF-1.4 second", "application/pdf")
        docs = db.get_documents(sid)
        self.assertEqual([doc["document_id"] for doc in docs], [second])
        self.assertTrue(Path(docs[0]["file_path"]).is_file())
        self.assertEqual(docs[0]["sha256"], hashlib.sha256(b"%PDF-1.4 second").hexdigest())
        self.assertEqual(docs[0]["supersedes_document_id"], first)
        self.assertEqual(db.get_documents(sid, include_history=True)[0]["file_name"], "first.pdf")
        self.assertEqual(len(db.get_documents(sid, include_history=True)), 2)

    def test_unsupported_document_rejected_without_file(self):
        sid = self.create()
        with self.assertRaises(ValueError):
            db.save_document(sid, "GST_CERTIFICATE", "bad.docx", b"bad", "application/msword")
        self.assertEqual(db.get_documents(sid), [])
        self.assertFalse(db.UPLOAD_DIR.exists())

    def test_database_insert_failure_removes_written_document(self):
        sid = self.create()
        c = db.get_connection()
        with c:
            c.execute("CREATE TRIGGER fail_document BEFORE INSERT ON vendor_documents BEGIN SELECT RAISE(FAIL,'Synthetic write failure'); END")
        c.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.docs(sid)
        self.assertEqual(db.get_documents(sid), [])
        self.assertEqual(list(db.UPLOAD_DIR.rglob("*.pdf")), [])

    def test_connection_failure_happens_before_document_write(self):
        sid = self.create()
        with patch.object(db, "get_connection", side_effect=sqlite3.OperationalError("Synthetic outage")):
            with self.assertRaises(sqlite3.OperationalError):
                self.docs(sid)
        self.assertFalse(db.UPLOAD_DIR.exists())

    def test_extraction_history_preserved(self):
        sid = self.create()
        doc_id = self.docs(sid)[0]
        db.save_extraction(doc_id, {"document_type": "GST_CERTIFICATE", "synthetic_revision": 1})
        db.save_extraction(doc_id, {"document_type": "GST_CERTIFICATE", "synthetic_revision": 2})
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM document_extractions"), 2)
        self.assertEqual(json.loads(db.get_documents(sid)[0]["extracted_data"])["synthetic_revision"], 2)
        with self.assertRaises(ValueError):
            db.save_extraction(99999, {})

    def test_resubmission_preserves_id_documents_events_and_inputs(self):
        sid = self.create()
        originals = self.docs(sid)
        db.save_check(sid, 1, {"code": "SYNTHETIC", "outcome": "PENDING", "message": "Correction needed."})
        db.update_status(sid, "PENDING", "Synthetic correction needed.")
        revision = db.revise_submission(sid, {"bank_name": "Corrected Synthetic Bank"}, 1, "Correct synthetic bank name.")
        self.assertEqual(revision, 2)
        self.assertEqual(db.get_submission(sid)["bank_name"], "Corrected Synthetic Bank")
        self.assertEqual(db.get_submission(sid)["status"], "SUBMITTED")
        self.assertEqual(len(db.get_revisions(sid)), 2)
        self.assertEqual([doc["document_id"] for doc in db.get_documents(sid, revision=1)], originals)
        self.assertEqual(len(db.get_documents(sid)), 2)
        self.assertEqual(len(db.get_documents(sid, include_history=True)), 4)
        self.assertEqual(db.get_checks(sid), [])
        self.assertEqual(len(db.get_checks(sid, 1)), 1)
        self.assertIn("RESUBMISSION_RECEIVED", {event["stage"] for event in db.get_events(sid)})
        self.assertIsNone(db.find_duplicate(DATA["tax_id"], sid))
        replacement = db.save_document(sid, "GST_CERTIFICATE", "corrected.pdf", b"%PDF-1.4 correction", "application/pdf", revision=2)
        self.assertIn(replacement, {doc["document_id"] for doc in db.get_documents(sid)})
        self.assertEqual(len(db.get_documents(sid, revision=1)), 2)
        self.assertEqual(len(db.get_documents(sid, include_history=True)), 5)
        c = db.get_connection()
        original = json.loads(c.execute("SELECT submitted_data FROM submission_revisions WHERE submission_id=? AND revision=1", (sid,)).fetchone()[0])
        c.close()
        self.assertEqual(original["bank_name"], DATA["bank_name"])

    def test_stale_and_active_revision_cannot_be_revised_or_processed(self):
        sid = self.create()
        db.begin_processing(sid, 1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.begin_processing(sid, 1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.revise_submission(sid, {}, 1)
        db.update_status(sid, "PENDING", "Synthetic interruption.")
        db.revise_submission(sid, {}, 1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.begin_processing(sid, 1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.save_document(sid, "GST_CERTIFICATE", "old.pdf", b"%PDF-1.4 old", "application/pdf", revision=1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.save_check(sid, 1, {"code": "OLD", "outcome": "PASS", "message": "Synthetic."})

    def test_checks_latest_view_retains_all_audit_events(self):
        sid = self.create()
        db.save_check(sid, 1, {"code": "SYNTHETIC", "outcome": "PENDING", "message": "First result."})
        db.save_check(sid, 1, {"code": "SYNTHETIC", "outcome": "PASS", "message": "Updated result."})
        self.assertEqual(db.get_checks(sid)[0]["outcome"], "PASS")
        self.assertEqual(len(db.get_checks(sid)), 1)
        self.assertEqual(len([event for event in db.get_events(sid) if event["stage"] == "SYNTHETIC"]), 2)

    def test_empty_failed_incomplete_and_unknown_checks_cannot_approve(self):
        for checks in ([], [{"code": "ONE", "outcome": "PASS", "message": "Synthetic."}],
                       [{"code": "ONE", "outcome": "FAIL", "message": "Synthetic failure."}],
                       [{"code": "ONE", "outcome": "ERROR", "message": "Synthetic error."}]):
            with self.subTest(checks=checks):
                sid = self.create(tax_id=f"SYNTHETIC-{self.scalar('SELECT COUNT(*) FROM vendor_submissions')}")
                self.docs(sid)
                db.begin_processing(sid, 1)
                self.assertEqual(db.finalize_decision(sid, 1, checks, "APPROVED", "Untrusted requested approval.", "demo_consistency")[0], "PENDING")

    def test_demo_approval_explicit_and_cannot_use_update_status(self):
        sid = self.create()
        self.docs(sid)
        with self.assertRaises(ValueError):
            db.update_status(sid, "APPROVED", "Bypass attempt.")
        db.begin_processing(sid, 1)
        self.assertEqual(db.finalize_decision(sid, 1, self.saved_passed_checks(sid), "APPROVED", "Synthetic consistency approval.", "demo_consistency")[0], "APPROVED")
        with self.assertRaises(db.ConcurrentUpdateError):
            db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Repeated completion.", "demo_consistency")
        with self.assertRaises(ValueError):
            db.revise_submission(sid, {}, 1)

    def test_unpersisted_pass_results_cannot_approve(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        status, _ = db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Caller-only passes.", "demo_consistency")
        self.assertEqual(status, "PENDING")

    def test_saved_failure_cannot_be_replaced_by_caller_passes(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        for check in passed_checks():
            saved = check | {"outcome": "FAIL", "message": "Actual saved mismatch."} if check["code"] == "SUBMITTED_BANK_HOLDER" else check
            db.save_check(sid, 1, saved)
        status, _ = db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Caller hides failure.", "demo_consistency")
        self.assertEqual(status, "PENDING")

    def test_previous_run_passes_cannot_complete_an_empty_retry(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        for check in passed_checks():
            db.save_check(sid, 1, check)
        db.fail_processing(sid, 1, "SyntheticInterruption")
        db.begin_processing(sid, 1)
        status, _ = db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Stale retry passes.", "demo_consistency")
        self.assertEqual(status, "PENDING")

    def test_demo_finalization_independently_blocks_failed_authenticity(self):
        sid = self.create()
        gst, _ = self.docs(sid)
        db.record_authenticity(gst, "VERIFICATION_FAILED", "AUTHORIZED_REVIEW", "Synthetic Reviewer", "SIMULATED_FAILURE")
        db.begin_processing(sid, 1)
        for check in passed_checks():
            db.save_check(sid, 1, check)
        status, _ = db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Caller hides review failure.", "demo_consistency")
        self.assertEqual(status, "PENDING")


    def test_extra_saved_error_cannot_be_omitted_by_caller(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        checks = self.saved_passed_checks(sid)
        db.save_check(sid, 1, {"code": "EXTRA_CONFIGURED_CHECK", "outcome": "ERROR", "message": "Additional verification failed."})
        status, _ = db.finalize_decision(sid, 1, checks, "APPROVED", "Caller hides extra error.", "demo_consistency")
        self.assertEqual(status, "PENDING")

    def test_different_pass_explanations_require_reprocessing(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        checks = self.saved_passed_checks(sid)
        checks[0] = checks[0] | {"message": "Different unsaved explanation."}
        status, reason = db.finalize_decision(sid, 1, checks, "APPROVED", "Untrusted explanation.", "demo_consistency")
        self.assertEqual(status, "PENDING")
        self.assertIn("differ", reason)

    def test_approval_reason_cannot_invent_independent_verification(self):
        sid = self.create()
        self.docs(sid)
        db.begin_processing(sid, 1)
        checks = self.saved_passed_checks(sid)
        status, reason = db.finalize_decision(sid, 1, checks, "APPROVED", "Government and bank certified this vendor.", "demo_consistency")
        self.assertEqual(status, "APPROVED")
        self.assertIn("NOT_VERIFIED", reason)
        self.assertNotIn("certified this vendor", reason)

    def test_duplicate_recheck_rejects_after_original_approval(self):
        first = self.create()
        self.docs(first)
        db.begin_processing(first, 1)
        self.assertEqual(db.finalize_decision(first, 1, self.saved_passed_checks(first), "APPROVED", "Synthetic approval.", "demo_consistency")[0], "APPROVED")
        second = self.create(tax_id=" 27 AB\tCDE1234F1Z5 ")
        self.docs(second)
        db.begin_processing(second, 1)
        self.assertEqual(db.finalize_decision(second, 1, self.saved_passed_checks(second), "APPROVED", "Stale duplicate result.", "demo_consistency")[0], "REJECTED")
        self.assertEqual(db.get_submission(first)["status"], "APPROVED")

    def test_active_duplicate_rejected_but_rejected_previous_can_retry(self):
        first = self.create()
        second = self.create()
        self.docs(second)
        db.begin_processing(second, 1)
        self.assertEqual(db.finalize_decision(second, 1, self.saved_passed_checks(second), "APPROVED", "Synthetic.", "demo_consistency")[0], "REJECTED")
        db.update_status(first, "REJECTED", "Synthetic rejected fixture.")
        db.begin_processing(second, 1)
        self.assertEqual(db.finalize_decision(second, 1, self.saved_passed_checks(second), "APPROVED", "Synthetic retry.", "demo_consistency")[0], "APPROVED")

    def test_atomic_duplicate_recheck_rejects_pending_regardless_of_requested_decision(self):
        for requested in ("APPROVED", "PENDING", "REJECTED"):
            with self.subTest(requested=requested):
                tax_id = "SYNTHETIC-DUPLICATE-" + requested
                original = self.create(tax_id=tax_id)
                db.update_status(original, "PENDING", "Synthetic original awaiting evidence.")
                duplicate = self.create(tax_id=tax_id)
                db.begin_processing(duplicate, 1)
                status, reason = db.finalize_decision(duplicate, 1, [], requested, "Stale caller result.", "demo_consistency")
                self.assertEqual(status, "REJECTED")
                self.assertIn(f"VND-{original:06d}", reason)
                self.assertEqual(db.get_submission(original)["status"], "PENDING")

    def test_strict_requires_authorized_hash_bound_document_evidence(self):
        sid = self.create()
        gst, bank = self.docs(sid)
        self.assertEqual(db.get_authenticity(gst)["state"], "NOT_VERIFIED")
        db.begin_processing(sid, 1)
        self.assertEqual(db.finalize_decision(sid, 1, self.saved_passed_checks(sid, "strict"), "APPROVED", "Untrusted strict approval.")[0], "PENDING")
        db.record_authenticity(gst, "VERIFIED", "GST_PORTAL_AND_ORIGINAL", "Synthetic Reviewer", "Synthetic authorized verification fixture")
        db.record_authenticity(bank, "VERIFIED", "BANK_CONFIRMATION", "Synthetic Reviewer", "Synthetic authorized verification fixture")
        db.begin_processing(sid, 1)
        self.assertEqual(db.finalize_decision(sid, 1, self.saved_passed_checks(sid, "strict"), "APPROVED", "Synthetic strict fixture.")[0], "APPROVED")
        self.assertEqual(db.get_authenticity(gst)["state"], "VERIFIED")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM authenticity_verifications"), 2)

    def test_review_withdrawal_revokes_approval_and_preserves_prior_decision(self):
        for policy, state in ((p, s) for p in ("strict", "demo_consistency") for s in ("NOT_VERIFIED", "VERIFICATION_FAILED")):
            with self.subTest(policy=policy, state=state):
                sid = self.create(tax_id="SYNTHETIC-" + policy + state)
                gst, bank = self.docs(sid)
                if policy == "strict":
                    for document in (gst, bank):
                        db.record_authenticity(document, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic Reviewer",
                                               "SIMULATED_UNIT_TEST_ONLY", "No real independent verification is claimed by this test.")
                db.begin_processing(sid, 1)
                self.assertEqual(db.finalize_decision(sid, 1, self.saved_passed_checks(sid, policy), "APPROVED", "Synthetic unit-test approval.", policy)[0], "APPROVED")
                db.record_authenticity(gst, state, "AUTHORIZED_REVIEW", "Synthetic Reviewer",
                                       "SIMULATED_WITHDRAWAL", "Unit-test review only.")
                self.assertEqual(db.get_submission(sid)["status"], "PENDING")
                self.assertEqual(db.get_authenticity(gst)["state"], state)
                self.assertEqual(next(c for c in db.get_checks(sid) if c["code"] == "GST_CERTIFICATE_AUTHENTICITY")["outcome"], "PENDING")
                decisions = [e["outcome"] for e in db.get_events(sid) if e["stage"] == "FINAL_DECISION"]
                self.assertEqual(decisions, ["APPROVED", "PENDING"])
                self.assertEqual(db.get_submission(sid)["current_revision"], 1)

    def test_all_review_states_require_a_reviewer_identity(self):
        sid = self.create(); gst = self.docs(sid)[0]
        for state in ("NOT_VERIFIED", "VERIFICATION_FAILED"):
            with self.subTest(state=state), self.assertRaises(ValueError):
                db.record_authenticity(gst, state, "AUTHORIZED_REVIEW", "", "Synthetic reference")

    def test_authenticity_rejects_ai_method_missing_reference_and_wrong_category(self):
        sid = self.create()
        gst, bank = self.docs(sid)
        for document_id, method, reviewer, reference in (
            (gst, "AI_VISUAL_INSPECTION", "Synthetic Reviewer", "Synthetic"),
            (gst, "AUTHORIZED_REVIEW", "", "Synthetic"),
            (gst, "AUTHORIZED_REVIEW", "Synthetic Reviewer", ""),
            (bank, "GST_PORTAL_AND_ORIGINAL", "Synthetic Reviewer", "Synthetic"),
        ):
            with self.subTest(method=method, reviewer=reviewer, reference=reference):
                with self.assertRaises(ValueError):
                    db.record_authenticity(document_id, "VERIFIED", method, reviewer, reference)
        self.assertEqual(db.get_authenticity(gst)["state"], "NOT_VERIFIED")

    def test_reviewer_cannot_attest_superseded_or_active_document(self):
        sid = self.create()
        old = self.docs(sid)[0]
        db.save_document(sid, "GST_CERTIFICATE", "replacement.pdf", b"%PDF-1.4 replacement", "application/pdf")
        with self.assertRaises(db.ConcurrentUpdateError):
            db.record_authenticity(old, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic", "Synthetic")
        current = db.get_documents(sid)[1]["document_id"]
        db.begin_processing(sid, 1)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.record_authenticity(current, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic", "Synthetic")

    def test_tampered_or_missing_files_cannot_approve_any_policy(self):
        for tamper in (True, False):
            sid = self.create(tax_id=f"SYNTHETIC-FILE-{tamper}")
            self.docs(sid)
            path = Path(db.get_documents(sid)[0]["file_path"])
            if tamper:
                path.write_bytes(b"changed synthetic fixture")
            else:
                path.unlink()
            db.begin_processing(sid, 1)
            self.assertEqual(db.finalize_decision(sid, 1, self.saved_passed_checks(sid), "APPROVED", "Synthetic.", "demo_consistency")[0], "PENDING")

    def test_tampered_document_cannot_receive_review(self):
        sid = self.create()
        gst = self.docs(sid)[0]
        Path(db.get_documents(sid)[0]["file_path"]).write_bytes(b"changed synthetic fixture")
        with self.assertRaises(ValueError):
            db.record_authenticity(gst, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic", "Synthetic")

    def test_verified_label_is_withheld_if_reviewed_file_changes(self):
        sid = self.create()
        gst = self.docs(sid)[0]
        db.record_authenticity(gst, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic Reviewer", "Synthetic authorized fixture")
        path = Path(db.get_documents(sid)[0]["file_path"])
        path.write_bytes(b"changed synthetic fixture")
        evidence = db.get_authenticity(gst)
        self.assertEqual(evidence["state"], "VERIFICATION_FAILED")
        self.assertEqual(evidence["recorded_state"], "VERIFIED")
        path.unlink()
        self.assertEqual(db.get_authenticity(gst)["state"], "VERIFICATION_FAILED")

    def test_resubmission_scopes_evidence_to_new_revision(self):
        sid = self.create()
        gst, bank = self.docs(sid)
        db.record_authenticity(gst, "VERIFIED", "AUTHORIZED_REVIEW", "Synthetic", "Synthetic authorized fixture")
        db.update_status(sid, "PENDING", "Correction required.")
        db.revise_submission(sid, {}, 1)
        current_gst = next(doc for doc in db.get_documents(sid) if doc["document_type"] == "GST_CERTIFICATE")
        self.assertEqual(db.get_authenticity(current_gst["document_id"])["state"], "NOT_VERIFIED")
        self.assertEqual(db.get_authenticity(gst)["state"], "VERIFIED")


    def test_unknown_application_rejected_and_transaction_rolled_back(self):
        with self.assertRaises(ValueError):
            db.begin_processing(9999, 1)
        with self.assertRaises(ValueError):
            db.update_status(9999, "PENDING", "Synthetic.")
        self.assertEqual(db.get_submissions(), [])

    def test_processing_failure_records_safe_type_and_never_approves(self):
        sid = self.create()
        db.begin_processing(sid, 1)
        status, reason = db.fail_processing(sid, 1, "TimeoutError")
        self.assertEqual(status, "PENDING")
        self.assertIn("interrupted", reason)
        self.assertEqual(db.get_submission(sid)["status"], "PENDING")
        self.assertIn("TimeoutError", [event["details"] for event in db.get_events(sid)])
        with self.assertRaises(db.ConcurrentUpdateError):
            db.fail_processing(sid, 1, "RepeatedError")

    def test_processing_failure_does_not_log_arbitrary_exception_payload(self):
        sid = self.create()
        db.begin_processing(sid, 1)
        db.fail_processing(sid, 1, "Synthetic API payload with sensitive material")
        event = next(event for event in db.get_events(sid) if event["stage"] == "PROCESSING_ERROR")
        self.assertEqual(event["details"], "ProcessingError")

    def test_reviewer_recovery_invalidates_original_worker_and_retains_history(self):
        sid = self.create()
        gst, bank = self.docs(sid)
        db.begin_processing(sid, 1)
        revision = db.recover_processing(sid, 1, "Synthetic Reviewer")
        self.assertEqual(revision, 2)
        self.assertEqual(db.get_submission(sid)["status"], "PENDING")
        self.assertEqual(len(db.get_documents(sid)), 2)
        self.assertEqual(len(db.get_documents(sid, include_history=True)), 4)
        self.assertEqual(len(db.get_revisions(sid)), 2)
        db.begin_processing(sid, 2)
        with self.assertRaises(db.ConcurrentUpdateError):
            db.save_check(sid, 1, {"code": "OLD", "outcome": "PASS", "message": "Synthetic."})
        with self.assertRaises(db.ConcurrentUpdateError):
            db.save_extraction(gst, {"document_type": "GST_CERTIFICATE"})
        with self.assertRaises(db.ConcurrentUpdateError):
            db.finalize_decision(sid, 1, passed_checks(), "APPROVED", "Synthetic.", "demo_consistency")
        with self.assertRaises(db.ConcurrentUpdateError):
            db.fail_processing(sid, 1, "StaleWorkerError")
        self.assertEqual(db.get_submission(sid)["status"], "PROCESSING")
        self.assertIn("PROCESSING_RECOVERED", [event["stage"] for event in db.get_events(sid)])

    def test_recovery_requires_current_active_revision_and_reviewer(self):
        sid = self.create()
        with self.assertRaises(db.ConcurrentUpdateError):
            db.recover_processing(sid, 1, "Synthetic Reviewer")
        db.begin_processing(sid, 1)
        with self.assertRaises(ValueError):
            db.recover_processing(sid, 1, "")
        with self.assertRaises(db.ConcurrentUpdateError):
            db.recover_processing(sid, 0, "Synthetic Reviewer")


    def test_concurrent_begin_processing_allows_only_one_worker(self):
        sid = self.create()
        barrier = threading.Barrier(2)
        results = []

        def run():
            barrier.wait(timeout=3)
            try:
                db.begin_processing(sid, 1)
                results.append("started")
            except db.ConcurrentUpdateError:
                results.append("blocked")

        workers = [threading.Thread(target=run) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)
        self.assertEqual(sorted(results), ["blocked", "started"])
        self.assertEqual(len([event for event in db.get_events(sid) if event["stage"] == "PROCESSING_STARTED"]), 1)


if __name__ == "__main__":
    unittest.main()
