"""VENDENCE navigation and workflow integration. Presentation lives in ui.py."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
import streamlit as st
from config import load_local_env, setting, public_configuration_errors

# Configuration must load before modules resolve persistent storage paths.
load_local_env()
import ui
import database as db
from workflow import process_application, record_document_review
from validation import missing_submission_requirements

st.set_page_config(page_title="VENDENCE · Vendor Onboarding", page_icon="✦",
                   layout="wide", initial_sidebar_state="expanded")
ui.configure_theme()


def configured(name, default=""):
    return setting(name, st.secrets, default)


def password_gate(name, title, state_key):
    password = configured(name)
    if not password:
        return False
    fingerprint = hashlib.sha256(password.encode()).hexdigest()
    if st.session_state.get(state_key) == fingerprint:
        return True
    with st.form(f"{state_key}_form"):
        entered = st.text_input(title, type="password")
        accepted = st.form_submit_button("Unlock", type="primary")
    if accepted:
        if hmac.compare_digest(entered.encode(), password.encode()):
            st.session_state[state_key] = fingerprint
            st.rerun()
        else:
            st.error("The password did not match.")
    return False


errors = public_configuration_errors()
if errors:
    st.error("Public startup requires secure configuration. " + " ".join(errors))
    st.stop()
if configured("VENDENCE_ACCESS_PASSWORD"):
    if not password_gate("VENDENCE_ACCESS_PASSWORD", "Workspace Access Password", "access_unlocked"):
        ui.header("WORKSPACE  /  ACCESS", "Welcome to VENDENCE.",
                  "Enter your workspace password to view vendor applications.")
        st.stop()


@st.cache_resource
def initialize_storage(path):
    db.initialize_database()
    return True


try:
    initialize_storage(str(db.DB_PATH))
except Exception:
    st.error("The application database is unavailable. Check the persistent storage configuration and restart.")
    st.stop()

policy = configured("VENDENCE_APPROVAL_POLICY", "strict")
api_key = configured("GEMINI_API_KEY")
model = configured("GEMINI_MODEL", "gemini-3.5-flash-lite")
page = ui.sidebar()
with st.sidebar:
    if policy == "demo_consistency":
        st.caption("Sample workspace")
    elif policy != "strict":
        st.warning("Verification is unavailable. Check the approval policy.")
    if configured("VENDENCE_QA_MODE") == "CONTROLLED GEMINI FAILURE":
        st.warning("Test mode: document processing is deliberately unavailable.")
    if configured("VENDENCE_ACCESS_PASSWORD") and st.button("Lock workspace"):
        st.session_state.clear()
        st.rerun()


def process_submission(data=None, uploaded_documents=None, **options):
    if not options.get("submission_id") and st.session_state.get("completed_onboarding_result"):
        # An already-consumed form event may arrive after the result was shown.
        st.rerun()
    if not options.get("reprocess"):
        saved_types = {doc["document_type"] for doc in db.get_documents(options["submission_id"])} if options.get("submission_id") else set()
        fields, documents = missing_submission_requirements(data or {}, uploaded_documents or {}, saved_types)
        if fields or documents:
            if fields:
                st.error("Complete the required fields: " + ", ".join(fields) + ".")
            if documents:
                st.error("Upload the required documents: " + ", ".join(documents) + ".")
            return
    # The operator declares a synthetic workspace at startup, outside the vendor form.
    synthetic_declared = policy == "demo_consistency" and (
        configured("VENDENCE_SYNTHETIC_DATA_ONLY", "0") == "1" or
        (options.get("reprocess", False) and st.session_state.get("review_synthetic_declared", False))
    )
    ui.section("Live verification", "Checking your application and supporting documents")
    with st.status("Processing application…", expanded=True) as progress:
        def on_stage(title, detail):
            st.write(f"**{title}**")
            st.caption(detail)
        result = process_application(
            data, uploaded_documents, policy=policy,
            synthetic_declared=synthetic_declared,
            api_key=api_key, model=model, on_stage=on_stage, **options,
        )
        progress.update(label="Processing interrupted" if result.error_code else "Verification finished",
                        state="error" if result.error_code else "complete", expanded=False)
    if result.submission_id is None:
        st.error("The application could not be saved. Check database availability and retry.")
        return
    st.session_state.focus_submission_id = result.submission_id
    if not options.get("submission_id"):
        st.session_state.completed_onboarding_result = result
        st.session_state.show_onboarding_dialog = True
        # Replace the submitted form, rather than leaving an active Submit button.
        st.rerun()
    show_submission_result(result)


def show_submission_result(result, *, show_dialog=True):
    ui.processing_result(result.submission_id, result.status, result.reason, result.checks)
    if result.persistence_warning:
        st.error("The latest failure state could not be saved. The displayed result is provisional; check database state after storage recovers.")
    if show_dialog:
        ui.submission_status_dialog(result.submission_id, result.status, result.reason, result.checks)


try:
    records = [dict(row) for row in db.get_submissions()]
    if page == "Overview":
        ui.overview(records, db.get_events)
    elif page == "New Onboarding":
        completed = st.session_state.get("completed_onboarding_result")
        if completed:
            current = db.get_submission(completed.submission_id)
            if current and not completed.persistence_warning:
                completed = replace(completed, status=current["status"],
                                    reason=current["decision_reason"],
                                    checks=db.get_checks(completed.submission_id))
            show_submission_result(completed, show_dialog=st.session_state.pop("show_onboarding_dialog", False))
        else:
            if not api_key:
                st.warning("Configure the Gemini API key before document extraction. See SETUP.md.")
            submitted = ui.onboarding_form(policy=policy, resumable_records=records)
            if submitted is not None:
                data, docs = submitted
                process_submission(data, docs)
    elif page == "Verification Center":
        selected_id = ui.verification(
            records, db.get_events, db.get_documents, db.DATA_DIR,
            check_loader=db.get_checks, authenticity_loader=db.get_authenticity,
            history_loader=lambda sid: db.get_documents(sid, include_history=True),
            revision_loader=db.get_revisions,
        )
        if selected_id is not None:
            current = db.get_submission(selected_id)
            revision = current["current_revision"]
            review_notice = st.session_state.pop("review_notice", None)
            if review_notice:
                st.success(review_notice)
            if current["status"] in {"PENDING", "REJECTED", "SUBMITTED"}:
                with st.expander("Correct information and resubmit", expanded=st.session_state.pop("open_correction_for", None) == selected_id):
                    submitted = ui.onboarding_form(initial=current, correction=True, policy=policy)
                    if submitted is not None:
                        data, docs = submitted
                        process_submission(data, docs, submission_id=selected_id,
                                           expected_revision=revision,
                                           correction_reason=st.session_state.get("correction_reason", "Vendor correction"))
            if configured("VENDENCE_REVIEWER_PASSWORD"):
                with st.expander("Reviewer access"):
                    if password_gate("VENDENCE_REVIEWER_PASSWORD", "Reviewer Password", "reviewer_unlocked"):
                        action = ui.reviewer_panel(current, db.get_documents(selected_id), db.get_authenticity)
                        if action:
                            if action["state"] == "VERIFIED" and not action.get("independent_checks_confirmed"):
                                st.error("Confirm that independent checks were performed before recording Verified.")
                            else:
                                try:
                                    record_document_review(selected_id, **{key: action[key] for key in (
                                        "document_id", "state", "method", "reviewer", "evidence_reference", "notes")})
                                    st.session_state.review_notice = "Review saved. Re-run verification to update the decision."
                                    st.rerun()
                                except Exception:
                                    st.error("The review could not be saved. Reload and verify the current document and evidence fields.")
                        if policy == "demo_consistency" and configured("VENDENCE_SYNTHETIC_DATA_ONLY", "0") != "1":
                            st.session_state.review_synthetic_declared = st.checkbox(
                                "I confirm this reprocessing uses synthetic demonstration data only.", key=f"review_synthetic_{selected_id}_{revision}")
                        if current["status"] == "PROCESSING":
                            st.warning("This application has an unfinished run. Recover only after confirming that the original worker has stopped.")
                            if st.button("Recover interrupted run", key=f"recover_{selected_id}_{revision}"):
                                db.recover_processing(selected_id, revision, actor="authorized reviewer")
                                st.rerun()
                        elif current["status"] != "APPROVED" and st.button("Re-run verification", key=f"reprocess_{selected_id}_{revision}", type="primary"):
                            process_submission(submission_id=selected_id, expected_revision=revision, reprocess=True)
    elif page == "Vendor Registry":
        ui.registry(records, db.get_events)
except Exception as error:
    st.error("This view could not load. Reload it; if application files were recently updated, restart Streamlit. Check storage availability if the problem persists. No approval was issued by this operation.")
    print("VENDENCE view error:", type(error).__name__, flush=True)

st.divider()
st.caption("VENDENCE · Vendor onboarding")
