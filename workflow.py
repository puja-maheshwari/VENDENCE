"""Executable onboarding service, shared by Streamlit and repeatable tests.

AI extracts evidence. validation.py decides; database.py commits the decision
for the current revision. The UI presents the recorded result and requirements.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import database as db
from ai_service import extract_document, validate_extraction
from validation import (
    check_required_fields, check_field_formats, inspect_document, check_duplicate,
    check_document_evidence, check_authenticity, check_approval_policy,
    required_check_codes, determine_decision, make_check,
)

DOCUMENT_TYPES = ("GST_CERTIFICATE", "BANK_PROOF")


@dataclass
class WorkflowResult:
    submission_id: int | None = None
    revision: int = 1
    status: str = "PENDING"
    reason: str = "Processing did not complete. Review is required."
    checks: list = field(default_factory=list)
    error_code: str = ""
    persistence_warning: bool = False


def record_document_review(submission_id, **review):
    """Record an authorized UI review and return the current decision.

    The caller enforces the reviewer gate. The document must belong to this
    application's current revision; persistence owns the atomic state change.
    """
    before = db.get_submission(submission_id)
    current_ids = {document["document_id"] for document in db.get_documents(submission_id)}
    if not before or review.get("document_id") not in current_ids:
        raise db.ConcurrentUpdateError("Review requires a current document in the selected application.")
    db.record_authenticity(**review)
    current = db.get_submission(submission_id)
    result = WorkflowResult(submission_id=submission_id, revision=current["current_revision"],
                            status=current["status"], reason=current["decision_reason"] or "Review recorded.")
    return result


def process_application(data=None, uploaded_documents=None, *, submission_id=None,
                        expected_revision=None, correction_reason="", reprocess=False,
                        policy="strict", synthetic_declared=False, api_key=None,
                        model=None, on_stage=None):
    """Create, correct, or reprocess a real application; no simulated stages.

    Missing correction uploads retain previous documents. An invalid replacement
    still fails the run and cannot fall back to approving the earlier document.
    Reprocessing preserves review evidence for the same revision.
    """
    result = WorkflowResult(submission_id=submission_id)
    owns_processing = False
    uploaded_documents = uploaded_documents or {}
    on_stage = on_stage or (lambda title, detail: None)

    def record(check):
        result.checks.append(check)
        db.save_check(result.submission_id, result.revision, check)

    try:
        on_stage("Application received", "Saving application information.")
        if submission_id is None:
            clean_data = {key: str((data or {}).get(key) or "").strip() for key in db.FIELDS}
            result.submission_id = db.create_vendor_submission(**clean_data)
            result.revision = 1
            data = clean_data
        else:
            current = db.get_submission(submission_id)
            if current is None:
                raise ValueError("Application does not exist.")
            expected_revision = expected_revision or current["current_revision"]
            if reprocess:
                result.revision = expected_revision
                data = current
            else:
                result.revision = db.revise_submission(
                    submission_id, data or {}, expected_revision, correction_reason,
                    replacement_types=[kind for kind in DOCUMENT_TYPES if uploaded_documents.get(kind) is not None],
                )
                data = db.get_submission(submission_id)
        db.begin_processing(result.submission_id, result.revision)
        owns_processing = True
        for check in check_approval_policy(policy, synthetic_declared=synthetic_declared):
            record(check)
        on_stage("Required information", "Checking mandatory company and banking fields.")
        for check in check_required_fields(data):
            record(check)
        on_stage("Tax and banking formats", "Checking structure and GSTIN checksum.")
        for check in check_field_formats(data):
            record(check)
        on_stage("Duplicate registration", "Comparing the normalized GSTIN with application history.")
        record(check_duplicate(db.find_duplicate(data.get("tax_id"), result.submission_id)))
        prior_documents = {d["document_type"]: d for d in db.get_documents(result.submission_id)}
        for document_type in DOCUMENT_TYPES:
            label = "GST certificate" if document_type == "GST_CERTIFICATE" else "bank proof"
            on_stage("Document verification", f"Inspecting {label}.")
            upload = uploaded_documents.get(document_type)
            saved = prior_documents.get(document_type)
            extracted = None
            if upload is not None or saved is None:
                document, upload_check = inspect_document(document_type, upload)
                record(upload_check)
                if document is None:
                    record(check_authenticity(document_type, policy=policy))
                    continue
                document_id = db.save_document(
                    result.submission_id, document_type, document["filename"],
                    document["content"], document["mime_type"], revision=result.revision,
                )
                saved = next(d for d in db.get_documents(result.submission_id)
                             if d["document_id"] == document_id)
                content, mime_type = document["content"], document["mime_type"]
            else:
                path = Path(saved["file_path"]).resolve()
                if not path.is_relative_to(db.UPLOAD_DIR.resolve()) or not path.is_file():
                    record(make_check(f"{document_type}_UPLOAD", "ERROR",
                                      "The saved supporting document is missing or unavailable."))
                    record(check_authenticity(document_type, policy=policy))
                    continue
                content = path.read_bytes()
                if saved.get("sha256") and hashlib.sha256(content).hexdigest() != saved["sha256"]:
                    record(make_check(f"{document_type}_UPLOAD", "ERROR",
                                      "Saved document integrity check failed. Upload the original again."))
                    record(check_authenticity(document_type, policy=policy))
                    continue
                class SavedUpload:
                    name = saved["file_name"]
                    def getvalue(self):
                        return content
                document, upload_check = inspect_document(document_type, SavedUpload())
                record(upload_check)
                if document is None:
                    record(check_authenticity(document_type, policy=policy))
                    continue
                mime_type = document["mime_type"]
                if saved.get("extracted_data"):
                    try:
                        extracted = validate_extraction(json.loads(saved["extracted_data"]))
                        db.log_event(result.submission_id, "EXTRACTION_REUSED", "SUCCESS",
                                     "Recorded extraction reused for the unchanged document.", revision=result.revision)
                    except (ValueError, TypeError):
                        extracted = None
            if extracted is None:
                on_stage("AI document extraction", f"Gemini is interpreting {label}.")
                extracted, error = extract_document(document_type, content, mime_type,
                                                     api_key=api_key, model=model)
                if error:
                    record(make_check(f"{document_type}_AI_EXTRACTION", "ERROR", error))
                    record(check_authenticity(document_type, db.get_authenticity(saved["document_id"]), policy))
                    continue
                # Validate even injected/test extractors; never trust a malformed result.
                extracted = validate_extraction(extracted)
                db.save_extraction(saved["document_id"], extracted)
            record(make_check(f"{document_type}_AI_EXTRACTION", "PASS",
                              "Document information extracted; independent authenticity is evaluated separately."))
            for check in check_document_evidence(document_type, data, extracted):
                record(check)
            record(check_authenticity(document_type, db.get_authenticity(saved["document_id"]), policy))
        # Explicitly persist all unexecuted requirements; stale results cannot fill gaps.
        completed = {check["code"] for check in result.checks}
        outcomes = {check["code"]: check["outcome"] for check in result.checks}
        for code in sorted(required_check_codes(policy) - completed):
            message = "This required check could not be completed; resolve earlier requirements and retry."
            for kind, label in (("GST_CERTIFICATE", "GST certificate"), ("BANK_PROOF", "Bank proof")):
                if not code.startswith(kind + "_"):
                    continue
                if outcomes.get(kind + "_UPLOAD") not in {None, "PASS"}:
                    message = f"{label} checks will continue after a readable, supported document is uploaded and the application is resubmitted."
                elif outcomes.get(kind + "_AI_EXTRACTION") not in {None, "PASS"}:
                    message = f"{label} comparisons could not run because extraction failed. Retry processing; a technical failure alone does not require replacing the document."
                elif outcomes.get(kind + "_IDENTITY") not in {None, "PASS"}:
                    message = f"{label} field comparisons will run after the incorrect document is replaced and the application is resubmitted."
            record(make_check(code, "PENDING", message))
        on_stage("Business decision", "Applying the configured deterministic approval rules.")
        result.status, result.reason = determine_decision(result.checks, policy=policy)
        result.status, result.reason = db.finalize_decision(
            result.submission_id, result.revision, result.checks,
            result.status, result.reason, policy=policy,
        )
        owns_processing = False
        return result
    except Exception as error:
        result.error_code = type(error).__name__
        result.status = "PENDING"
        result.reason = ("This application changed in another session. Reload before retrying."
                         if isinstance(error, db.ConcurrentUpdateError) else
                         "Processing was interrupted. Resolve the technical issue and reprocess; no approval was issued by this run.")
        if owns_processing:
            incomplete_write = False
            completed = {check["code"] for check in result.checks}
            for code in sorted(required_check_codes(policy) - completed):
                try:
                    record(make_check(code, "ERROR", "This check was not completed because processing was interrupted."))
                except Exception:
                    incomplete_write = True
            try:
                db.fail_processing(result.submission_id, result.revision, result.error_code)
                if incomplete_write:
                    result.persistence_warning = True
                    result.reason += " Some interrupted checks could not be saved; review the audit after storage recovers."
            except Exception:
                result.persistence_warning = True
                result.reason += " The failure could not be written to the database; check storage availability."
        return result
