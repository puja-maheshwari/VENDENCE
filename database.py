"""SQLite persistence, immutable document files, and revision-scoped audit records."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from validation import check_authenticity, check_duplicate, determine_decision, normalize_code

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("VENDENCE_DATA_DIR") or BASE_DIR).expanduser().resolve()
DB_PATH = DATA_DIR / "database" / "vendence.db"
UPLOAD_DIR = DATA_DIR / "uploads"
FIELDS = (
    "vendor_name", "email", "country", "tax_id", "bank_account_holder",
    "bank_name", "bank_account_number", "ifsc_code",
)
AUTHENTICITY_METHODS = {
    "GST_CERTIFICATE": {"GST_PORTAL_AND_ORIGINAL", "TRUSTED_DIGITAL_SIGNATURE", "AUTHORIZED_REVIEW"},
    "BANK_PROOF": {"BANK_CONFIRMATION", "AUTHORIZED_REVIEW"},
}


class ConcurrentUpdateError(RuntimeError):
    """A stale revision or an active processing run cannot be overwritten."""


def _safe_note(value):
    """Free-text audit notes must not expose a full numeric bank identifier."""
    return re.sub(r"\d(?:[ -]?\d){8,}", "[number hidden]", str(value or ""))[:3000]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.create_function("normalize_identifier", 1, normalize_code, deterministic=True)
    return connection


def _current_revision(connection, submission_id):
    row = connection.execute(
        "SELECT current_revision,status FROM vendor_submissions WHERE submission_id=?", (submission_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Application does not exist.")
    return row


def _event(connection, submission_id, stage, outcome, details, revision=None, actor="system"):
    if revision is None:
        revision = _current_revision(connection, submission_id)["current_revision"]
    connection.execute(
        "INSERT INTO processing_events (submission_id,stage,outcome,details,revision,actor) VALUES (?,?,?,?,?,?)",
        (submission_id, stage, outcome, str(details), revision, actor),
    )


def initialize_database():
    """Additive, repeatable migrations; existing rows and files are preserved."""
    connection = get_connection()
    try:
        previous_version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        for statement in (
            """CREATE TABLE IF NOT EXISTS vendor_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT NOT NULL, email TEXT NOT NULL, country TEXT NOT NULL,
                tax_id TEXT, bank_account_holder TEXT, bank_name TEXT,
                bank_account_number TEXT, ifsc_code TEXT,
                status TEXT NOT NULL DEFAULT 'SUBMITTED', decision_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS vendor_documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL,
                document_type TEXT NOT NULL, file_name TEXT NOT NULL, file_path TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(submission_id) REFERENCES vendor_submissions(submission_id))""",
            """CREATE TABLE IF NOT EXISTS processing_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL,
                stage TEXT NOT NULL, outcome TEXT NOT NULL, details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(submission_id) REFERENCES vendor_submissions(submission_id))""",
        ):
            connection.execute(statement)
        migrations = {
            "vendor_submissions": {
                "bank_name": "TEXT", "bank_account_number": "TEXT", "ifsc_code": "TEXT",
                "current_revision": "INTEGER NOT NULL DEFAULT 1", "normalized_tax_id": "TEXT",
                "processing_check_start_id": "INTEGER NOT NULL DEFAULT 0",
            },
            "vendor_documents": {
                "extracted_data": "TEXT", "revision": "INTEGER NOT NULL DEFAULT 1",
                "sha256": "TEXT", "mime_type": "TEXT", "supersedes_document_id": "INTEGER",
            },
            "processing_events": {"revision": "INTEGER NOT NULL DEFAULT 1", "actor": "TEXT DEFAULT 'system'"},
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            for name, declaration in columns.items():
                if name not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_vendor_tax_id ON vendor_submissions(tax_id)",
            "CREATE INDEX IF NOT EXISTS idx_vendor_normalized_tax_id ON vendor_submissions(normalized_tax_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_revision ON vendor_documents(submission_id, revision, document_type)",
            "CREATE INDEX IF NOT EXISTS idx_event_submission ON processing_events(submission_id,event_id)",
            """CREATE TABLE IF NOT EXISTS submission_revisions (
                submission_id INTEGER NOT NULL, revision INTEGER NOT NULL, submitted_data TEXT NOT NULL,
                correction_reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(submission_id,revision),
                FOREIGN KEY(submission_id) REFERENCES vendor_submissions(submission_id))""",
            """CREATE TABLE IF NOT EXISTS verification_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL,
                revision INTEGER NOT NULL, code TEXT NOT NULL, outcome TEXT NOT NULL,
                message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(submission_id) REFERENCES vendor_submissions(submission_id))""",
            """CREATE TABLE IF NOT EXISTS document_extractions (
                extraction_id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
                extracted_data TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(document_id) REFERENCES vendor_documents(document_id))""",
            """CREATE TABLE IF NOT EXISTS authenticity_verifications (
                verification_id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
                submission_id INTEGER NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('VERIFIED','NOT_VERIFIED','VERIFICATION_FAILED')),
                method TEXT NOT NULL, reviewer TEXT NOT NULL, evidence_reference TEXT NOT NULL,
                notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(document_id) REFERENCES vendor_documents(document_id))""",
        ):
            connection.execute(statement)
        for row in connection.execute("SELECT * FROM vendor_submissions").fetchall():
            connection.execute(
                "UPDATE vendor_submissions SET normalized_tax_id=? WHERE submission_id=?",
                (normalize_code(row["tax_id"]), row["submission_id"]),
            )
            connection.execute(
                "INSERT OR IGNORE INTO submission_revisions (submission_id,revision,submitted_data,correction_reason,created_at) VALUES (?,?,?,?,?)",
                (row["submission_id"], row["current_revision"], json.dumps({key: row[key] for key in FIELDS}),
                 "Initial application / legacy migration", row["created_at"]),
            )
        # Legacy extraction payloads need one migration into the history table.
        # Current revisions deliberately reuse payloads without a new AI call;
        # restarting must not manufacture a fresh extraction-history entry.
        if previous_version < 3:
            connection.execute("""INSERT INTO document_extractions(document_id,extracted_data)
                SELECT d.document_id,d.extracted_data FROM vendor_documents d
                WHERE d.extracted_data IS NOT NULL AND NOT EXISTS
                (SELECT 1 FROM document_extractions e WHERE e.document_id=d.document_id)""")
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_vendor_submission(vendor_name, email, country, tax_id, bank_account_holder,
                             bank_name, bank_account_number, ifsc_code):
    data = dict(zip(FIELDS, (vendor_name, email, country, tax_id, bank_account_holder,
                            bank_name, bank_account_number, ifsc_code)))
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                f"INSERT INTO vendor_submissions ({','.join(FIELDS)},normalized_tax_id,status) VALUES ({','.join('?' for _ in FIELDS)},?,'SUBMITTED')",
                tuple(data.values()) + (normalize_code(tax_id),),
            )
            submission_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO submission_revisions(submission_id,revision,submitted_data,correction_reason) VALUES (?,1,?,?)",
                (submission_id, json.dumps(data), "Initial application"),
            )
            _event(connection, submission_id, "SUBMISSION_RECEIVED", "SUCCESS", "Vendor registration received.", 1)
        return submission_id
    finally:
        connection.close()


def get_submission(submission_id):
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM vendor_submissions WHERE submission_id=?", (submission_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def _effective_documents(connection, submission_id, revision):
    return connection.execute("""SELECT d.* FROM vendor_documents d
        WHERE d.submission_id=? AND d.revision=? AND NOT EXISTS
        (SELECT 1 FROM vendor_documents newer WHERE newer.submission_id=d.submission_id
         AND newer.revision=d.revision AND newer.document_type=d.document_type
         AND newer.document_id>d.document_id) ORDER BY d.document_id""", (submission_id, revision)).fetchall()


def _copy_documents(connection, submission_id, old_revision, new_revision, excluded_types=()):
    for doc in _effective_documents(connection, submission_id, old_revision):
        if doc["document_type"] in excluded_types:
            continue
        connection.execute("""INSERT INTO vendor_documents
            (submission_id,document_type,file_name,file_path,extracted_data,revision,sha256,mime_type,supersedes_document_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (submission_id, doc["document_type"], doc["file_name"], doc["file_path"], doc["extracted_data"],
             new_revision, doc["sha256"], doc["mime_type"], doc["document_id"]),
        )


def revise_submission(submission_id, data, expected_revision, correction_reason="", replacement_types=()):
    """Create a revision, retaining earlier inputs and document versions for auditing."""
    if set(replacement_types) - {"GST_CERTIFICATE", "BANK_PROOF"}:
        raise ValueError("Unsupported replacement category.")
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)
        if current["current_revision"] != expected_revision or current["status"] == "PROCESSING":
            raise ConcurrentUpdateError("Application changed or is currently processing. Reload and retry.")
        if current["status"] == "APPROVED":
            raise ValueError("Approved applications require a separate authorized change process.")
        old = connection.execute("SELECT * FROM vendor_submissions WHERE submission_id=?", (submission_id,)).fetchone()
        new_data = {key: data.get(key, old[key]) for key in FIELDS}
        revision = expected_revision + 1
        connection.execute(
            f"UPDATE vendor_submissions SET {','.join(f'{key}=?' for key in FIELDS)}, normalized_tax_id=?,current_revision=?,status='SUBMITTED',decision_reason=NULL,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?",
            tuple(new_data.values()) + (normalize_code(new_data["tax_id"]), revision, submission_id),
        )
        connection.execute(
            "INSERT INTO submission_revisions(submission_id,revision,submitted_data,correction_reason) VALUES (?,?,?,?)",
            (submission_id, revision, json.dumps(new_data), _safe_note(correction_reason)),
        )
        _copy_documents(connection, submission_id, expected_revision, revision, excluded_types=replacement_types)
        _event(connection, submission_id, "CORRECTION_SAVED", "SUCCESS", "Corrected application information saved; previous revision retained.", revision, "vendor")
        _event(connection, submission_id, "RESUBMISSION_RECEIVED", "SUCCESS", "Application resubmitted for verification.", revision, "vendor")
        connection.commit()
        return revision
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def begin_processing(submission_id, expected_revision):
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)
        if current["current_revision"] != expected_revision or current["status"] == "PROCESSING":
            raise ConcurrentUpdateError("Application changed or is already processing.")
        boundary = connection.execute(
            "SELECT COALESCE(MAX(check_id),0) FROM verification_checks WHERE submission_id=? AND revision=?",
            (submission_id, expected_revision),
        ).fetchone()[0]
        connection.execute("UPDATE vendor_submissions SET status='PROCESSING',processing_check_start_id=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (boundary, submission_id))
        _event(connection, submission_id, "PROCESSING_STARTED", "SUCCESS", "Verification workflow started.", expected_revision)
        connection.commit()
        return expected_revision
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fail_processing(submission_id, revision, error_code):
    """Fail only the active revision, recording an exception type rather than its payload."""
    safe_code = str(error_code) if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", str(error_code)) else "ProcessingError"
    reason = "Processing was interrupted; the application requires review."
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)
        if current["current_revision"] != revision or current["status"] != "PROCESSING":
            raise ConcurrentUpdateError("Cannot fail a stale or inactive verification run.")
        connection.execute("UPDATE vendor_submissions SET status='PENDING',decision_reason=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (reason, submission_id))
        _event(connection, submission_id, "PROCESSING_ERROR", "ERROR", safe_code, revision)
        _event(connection, submission_id, "FINAL_DECISION", "PENDING", reason, revision)
        connection.commit()
        return "PENDING", reason
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def recover_processing(submission_id, expected_revision, actor):
    """Reviewer recovery advances the revision, invalidating the interrupted worker."""
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("An authorized reviewer identity is required for recovery.")
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)
        if current["current_revision"] != expected_revision or current["status"] != "PROCESSING":
            raise ConcurrentUpdateError("Only the current interrupted processing revision can be recovered.")
        revision = expected_revision + 1
        old = connection.execute("SELECT * FROM vendor_submissions WHERE submission_id=?", (submission_id,)).fetchone()
        reason = "An authorized reviewer recovered interrupted processing; verification must run again."
        connection.execute("UPDATE vendor_submissions SET current_revision=?,status='PENDING',decision_reason=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (revision, reason, submission_id))
        connection.execute("INSERT INTO submission_revisions(submission_id,revision,submitted_data,correction_reason) VALUES (?,?,?,?)", (submission_id, revision, json.dumps({key: old[key] for key in FIELDS}), "Reviewer recovery of interrupted processing"))
        _copy_documents(connection, submission_id, expected_revision, revision)
        _event(connection, submission_id, "PROCESSING_RECOVERED", "SUCCESS", reason, revision, actor.strip())
        connection.commit()
        return revision
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def log_event(submission_id, stage, outcome, details, revision=None, actor="system"):
    connection = get_connection()
    try:
        with connection:
            _event(connection, submission_id, stage, outcome, details, revision, actor)
    finally:
        connection.close()


def update_status(submission_id, status, reason):
    """Compatibility API for safe fallback states; approvals require finalization."""
    if status not in {"SUBMITTED", "PROCESSING", "APPROVED", "PENDING", "REJECTED"}:
        raise ValueError("Unsupported application status.")
    if status == "APPROVED":
        raise ValueError("Approval requires revision-scoped finalize_decision checks.")
    connection = get_connection()
    try:
        with connection:
            revision = _current_revision(connection, submission_id)["current_revision"]
            connection.execute("UPDATE vendor_submissions SET status=?,decision_reason=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (status, reason, submission_id))
            _event(connection, submission_id, "FINAL_DECISION", status, reason, revision)
    finally:
        connection.close()


def _duplicate(connection, tax_id, current_submission_id):
    normalized = normalize_code(tax_id)
    if not normalized:
        return None
    # Also covers rows written by older app versions without the normalized column.
    return connection.execute("""SELECT submission_id,status FROM vendor_submissions
        WHERE normalize_identifier(tax_id)=? AND submission_id!=?
        ORDER BY CASE WHEN status='APPROVED' THEN 0 WHEN status='REJECTED' THEN 2 ELSE 1 END,
        submission_id DESC LIMIT 1""", (normalized, current_submission_id)).fetchone()


def find_duplicate(tax_id, current_submission_id):
    connection = get_connection()
    try:
        row = _duplicate(connection, tax_id, current_submission_id)
        return dict(row) if row else None
    finally:
        connection.close()


def save_check(submission_id, revision, check):
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _current_revision(connection, submission_id)["current_revision"] != revision:
            raise ConcurrentUpdateError("Cannot save a check for a stale revision.")
        connection.execute("INSERT INTO verification_checks(submission_id,revision,code,outcome,message) VALUES (?,?,?,?,?)",
                           (submission_id, revision, check["code"], check["outcome"], check["message"]))
        _event(connection, submission_id, check["code"], check["outcome"], check["message"], revision)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_checks(submission_id, revision=None):
    connection = get_connection()
    try:
        revision = revision or _current_revision(connection, submission_id)["current_revision"]
        rows = connection.execute("SELECT code,outcome,message,created_at FROM verification_checks WHERE submission_id=? AND revision=? ORDER BY check_id", (submission_id, revision)).fetchall()
        latest = {row["code"]: dict(row) for row in rows}
        return list(latest.values())
    finally:
        connection.close()


def finalize_decision(submission_id, revision, checks, status, reason, policy="strict"):
    """Commit against durable results from this run, with atomic safety rechecks."""
    if status not in {"APPROVED", "PENDING", "REJECTED"}:
        raise ValueError("Invalid final decision.")
    checks = list(checks or [])
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)
        if current["current_revision"] != revision or current["status"] != "PROCESSING":
            raise ConcurrentUpdateError("This verification run is stale or is no longer active.")
        if status == "APPROVED":
            checked_status, checked_reason = determine_decision(checks, policy=policy)
            if checked_status != "APPROVED":
                status, reason = checked_status, checked_reason
            else:
                boundary = connection.execute(
                    "SELECT processing_check_start_id FROM vendor_submissions WHERE submission_id=?",
                    (submission_id,),
                ).fetchone()[0]
                rows = connection.execute(
                    "SELECT code,outcome,message FROM verification_checks WHERE submission_id=? AND revision=? AND check_id>? ORDER BY check_id",
                    (submission_id, revision, boundary),
                ).fetchall()
                saved = {row["code"]: dict(row) for row in rows}
                saved_status, saved_reason = determine_decision(list(saved.values()), policy=policy)
                supplied = {check["code"]: dict(check) for check in checks}
                if saved_status != "APPROVED":
                    status, reason = saved_status, saved_reason
                elif saved != supplied:
                    status, reason = "PENDING", "Saved verification results differ from this run's results. Reprocess before approval."
                else:
                    # Approval wording comes from the policy, never arbitrary caller text.
                    reason = checked_reason
        row = connection.execute("SELECT tax_id FROM vendor_submissions WHERE submission_id=?", (submission_id,)).fetchone()
        duplicate = _duplicate(connection, row["tax_id"], submission_id)
        duplicate_check = check_duplicate(dict(duplicate) if duplicate else None)
        if duplicate_check["outcome"] == "REJECTED":
            status, reason = "REJECTED", duplicate_check["message"]
            _event(connection, submission_id, "DUPLICATE_RECHECK", "REJECTED", reason, revision)
        elif status == "APPROVED" and duplicate_check["outcome"] != "PASS":
            status, reason = "PENDING", duplicate_check["message"]
        if status == "APPROVED":
            docs = _effective_documents(connection, submission_id, revision)
            if {doc["document_type"] for doc in docs} != {"GST_CERTIFICATE", "BANK_PROOF"}:
                status, reason = "PENDING", "Required supporting documents are incomplete."
            for doc in docs:
                path = Path(doc["file_path"])
                if not path.resolve().is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
                    status, reason = "PENDING", "A saved supporting document is unavailable; review is required."
                    break
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if doc["sha256"] and digest != doc["sha256"]:
                    status, reason = "PENDING", "A saved document changed after upload; review is required."
                    break
                evidence = connection.execute("SELECT * FROM authenticity_verifications WHERE document_id=? ORDER BY verification_id DESC LIMIT 1", (doc["document_id"],)).fetchone()
                authenticity = check_authenticity(doc["document_type"], dict(evidence) if evidence else None, policy)
                if authenticity["outcome"] != "PASS":
                    status, reason = "PENDING", authenticity["message"]
                    break
                if policy == "strict" and (not evidence or evidence["state"] != "VERIFIED" or digest != evidence["sha256"]):
                    status, reason = "PENDING", "Independent authenticity verification is incomplete or the evidence file has changed."
                    break
            if not docs:
                status, reason = "PENDING", "Required supporting documents are incomplete."
        if policy not in {"strict", "demo_consistency"}:
            status, reason = "PENDING", "Unknown approval policy requires configuration review."
        connection.execute("UPDATE vendor_submissions SET status=?,decision_reason=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (status, reason, submission_id))
        _event(connection, submission_id, "FINAL_DECISION", status, reason, revision)
        connection.commit()
        return status, reason
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_document(submission_id, document_type, original_filename, content, mime_type, revision=None):
    extension_map = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}
    if mime_type not in extension_map:
        raise ValueError("Unsupported document format.")
    connection = get_connection()
    file_path = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _current_revision(connection, submission_id)["current_revision"]
        revision = current if revision is None else revision
        if revision != current:
            raise ConcurrentUpdateError("Cannot upload a document to a stale revision.")
        directory = UPLOAD_DIR / str(submission_id)
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / f"{uuid4().hex}{extension_map[mime_type]}"
        file_path.write_bytes(content)
        previous = connection.execute("SELECT document_id FROM vendor_documents WHERE submission_id=? AND revision=? AND document_type=? ORDER BY document_id DESC LIMIT 1", (submission_id, revision, document_type)).fetchone()
        cursor = connection.execute("""INSERT INTO vendor_documents
            (submission_id,document_type,file_name,file_path,revision,sha256,mime_type,supersedes_document_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (submission_id, document_type, Path(original_filename).name, str(file_path), revision,
             hashlib.sha256(content).hexdigest(), mime_type, previous[0] if previous else None),
        )
        _event(connection, submission_id, "DOCUMENT_STORED", "SUCCESS", f"{document_type.replace('_',' ').title()} stored; previous versions retained.", revision)
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        if file_path is not None:
            file_path.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def save_extraction(document_id, extracted_data):
    payload = json.dumps(extracted_data)
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        doc = connection.execute("SELECT submission_id,revision FROM vendor_documents WHERE document_id=?", (document_id,)).fetchone()
        if doc is None:
            raise ValueError("Document does not exist.")
        current = _current_revision(connection, doc["submission_id"])
        current_ids = {row["document_id"] for row in _effective_documents(connection, doc["submission_id"], current["current_revision"])}
        if doc["revision"] != current["current_revision"] or document_id not in current_ids:
            raise ConcurrentUpdateError("Cannot save extraction for a stale or superseded document.")
        connection.execute("UPDATE vendor_documents SET extracted_data=? WHERE document_id=?", (payload, document_id))
        connection.execute("INSERT INTO document_extractions(document_id,extracted_data) VALUES (?,?)", (document_id, payload))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_authenticity(document_id, state, method, reviewer, evidence_reference, notes=""):
    """Persist a reviewer attestation; never infer authenticity from AI headings."""
    if state not in {"VERIFIED", "NOT_VERIFIED", "VERIFICATION_FAILED"}:
        raise ValueError("Invalid authenticity state.")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Every verification review requires an authorized reviewer identity.")
    if state == "VERIFIED" and (not reviewer.strip() or not evidence_reference.strip()):
        raise ValueError("Verified status requires an authorized reviewer, independent method, and evidence reference.")
    reviewer, evidence_reference, notes = (_safe_note(value) for value in (reviewer, evidence_reference, notes))
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        doc = connection.execute("SELECT * FROM vendor_documents WHERE document_id=?", (document_id,)).fetchone()
        if doc is None:
            raise ValueError("Document does not exist.")
        if state == "VERIFIED" and method not in AUTHENTICITY_METHODS.get(doc["document_type"], set()):
            raise ValueError("This verification method is not authorized for the document category.")
        current = _current_revision(connection, doc["submission_id"])
        effective_ids = {row["document_id"] for row in _effective_documents(connection, doc["submission_id"], current["current_revision"])}
        if doc["revision"] != current["current_revision"] or document_id not in effective_ids or current["status"] == "PROCESSING":
            raise ConcurrentUpdateError("Review requires the current document and an idle application.")
        path = Path(doc["file_path"])
        if not path.is_file():
            raise FileNotFoundError("Saved document is unavailable for verification.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if doc["sha256"] and digest != doc["sha256"]:
            raise ValueError("Saved document integrity check failed.")
        cursor = connection.execute("""INSERT INTO authenticity_verifications
            (document_id,submission_id,revision,sha256,state,method,reviewer,evidence_reference,notes)
            VALUES (?,?,?,?,?,?,?,?,?)""", (document_id, doc["submission_id"], doc["revision"], digest, state, method, reviewer.strip(), evidence_reference.strip(), notes))
        _event(connection, doc["submission_id"], "AUTHENTICITY_REVIEW", state,
               f"{doc['document_type'].replace('_',' ').title()}: {state.replace('_',' ').title()} via {method.replace('_',' ').title()}; evidence reference recorded.", doc["revision"], reviewer.strip())
        if state != "VERIFIED" and current["status"] == "APPROVED":
            label = "GST certificate" if doc["document_type"] == "GST_CERTIFICATE" else "bank proof"
            reason = (f"Independent verification failed for the {label}. Correct the evidence or complete authorized review, then re-run verification."
                      if state == "VERIFICATION_FAILED" else
                      f"An authorized reviewer withdrew verification of the {label}. Review the evidence and re-run verification before approval.")
            connection.execute("UPDATE vendor_submissions SET status='PENDING',decision_reason=?,updated_at=CURRENT_TIMESTAMP WHERE submission_id=?", (reason, doc["submission_id"]))
            code = doc["document_type"] + "_AUTHENTICITY"
            connection.execute("INSERT INTO verification_checks(submission_id,revision,code,outcome,message) VALUES (?,?,?,'PENDING',?)",
                               (doc["submission_id"], doc["revision"], code, reason))
            _event(connection, doc["submission_id"], code, "PENDING", reason, doc["revision"], reviewer.strip())
            _event(connection, doc["submission_id"], "APPROVAL_WITHDRAWN", "PENDING", reason, doc["revision"], reviewer.strip())
            _event(connection, doc["submission_id"], "FINAL_DECISION", "PENDING", reason, doc["revision"], reviewer.strip())
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_authenticity(document_id):
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM authenticity_verifications WHERE document_id=? ORDER BY verification_id DESC LIMIT 1", (document_id,)).fetchone()
        if row is None:
            return {"state": "NOT_VERIFIED", "method": "", "reviewer": "", "evidence_reference": ""}
        evidence = dict(row)
        if evidence["state"] == "VERIFIED":
            doc = connection.execute("SELECT file_path FROM vendor_documents WHERE document_id=?", (document_id,)).fetchone()
            path = Path(doc["file_path"]) if doc else None
            try:
                valid = path is not None and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == evidence["sha256"]
            except OSError:
                valid = False
            if not valid:
                evidence.update(state="VERIFICATION_FAILED", recorded_state="VERIFIED",
                                integrity_error="Saved document is unavailable or no longer matches the reviewed file.")
        return evidence
    finally:
        connection.close()


def get_submissions():
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("""SELECT submission_id,vendor_name,email,tax_id,status,
            decision_reason,created_at,updated_at,current_revision FROM vendor_submissions ORDER BY submission_id DESC""")]
    finally:
        connection.close()


def get_events(submission_id):
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("SELECT event_id,stage,outcome,details,created_at,revision,actor FROM processing_events WHERE submission_id=? ORDER BY event_id", (submission_id,))]
    finally:
        connection.close()


def get_documents(submission_id, revision=None, include_history=False):
    connection = get_connection()
    try:
        if include_history:
            return [dict(row) for row in connection.execute("SELECT * FROM vendor_documents WHERE submission_id=? ORDER BY document_id", (submission_id,))]
        revision = revision or _current_revision(connection, submission_id)["current_revision"]
        return [dict(row) for row in _effective_documents(connection, submission_id, revision)]
    finally:
        connection.close()


def get_revisions(submission_id):
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("SELECT revision,correction_reason,created_at FROM submission_revisions WHERE submission_id=? ORDER BY revision", (submission_id,))]
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print("VENDENCE database initialized successfully!")
