"""VENDENCE presentation layer: styling, pages, and readable audit displays.

No business decisions, Gemini calls, or SQLite writes belong in this file.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd
import streamlit as st


PAGES = (
    ("Overview", "◫"),
    ("New Onboarding", "＋"),
    ("Verification Center", "✧"),
    ("Vendor Registry", "▤"),
)

# Common choices, not an exhaustive registry. Unlisted names remain enterable.
BANK_NAMES = (
    "Axis Bank", "Bank of Baroda", "Bank of India", "Bank of Maharashtra",
    "Canara Bank", "Central Bank of India", "Federal Bank", "HDFC Bank",
    "ICICI Bank", "IDBI Bank", "IDFC FIRST Bank", "Indian Bank",
    "Indian Overseas Bank", "IndusInd Bank", "Kotak Mahindra Bank",
    "Punjab & Sind Bank", "Punjab National Bank", "State Bank of India",
    "UCO Bank", "Union Bank of India",
)

FIELD_LABELS = {
    "vendor_name": "Legal Company Name",
    "email": "Business Email",
    "tax_id": "GSTIN",
    "gstin": "GSTIN",
    "country": "Country",
    "bank_name": "Bank Name",
    "bank_account_holder": "Bank Account Holder",
    "account_holder": "Account Holder",
    "bank_account_number": "Bank Account Number",
    "account_number": "Account Number",
    "ifsc": "IFSC Code",
    "ifsc_code": "IFSC Code",
    "document_type": "Document Type",
    "document_subtype": "Document Subtype",
    "legal_name": "Registered Legal Name",
    "trade_name": "Trade Name",
    "registration_form": "Registration Form",
    "document_title": "Document Title",
    "classification_evidence": "Classification Evidence",
}

EVENT_LABELS = {
    "SUBMISSION_RECEIVED": "Application Received",
    "SUBMISSION_CREATED": "Application Created",
    "PROCESSING_STARTED": "Verification Started",
    "PROCESSING_ERROR": "Processing Interrupted",
    "DOCUMENT_STORED": "Document Saved",
    "DUPLICATE_CHECK": "Duplicate Registration Checked",
    "FINAL_DECISION": "Decision Recorded",
    "GST_CERTIFICATE_AI_EXTRACTION": "GST Certificate Analyzed",
    "BANK_PROOF_AI_EXTRACTION": "Bank Document Analyzed",
    "RESUBMISSION_RECEIVED": "Resubmission Received",
    "CORRECTION_SAVED": "Corrections Saved",
    "AUTHENTICITY_REVIEW": "Document Verification Recorded",
    "APPROVAL_WITHDRAWN": "Approval Withdrawn After Review",
    "GST_CERTIFICATE_AUTHENTICITY": "GST Authenticity Policy Check",
    "BANK_PROOF_AUTHENTICITY": "Bank Authenticity Policy Check",
    "APPROVAL_POLICY": "Approval Policy",
    "SYNTHETIC_DATA_DECLARED": "Synthetic Demonstration Declared",
}
ACRONYMS = {"AI", "GST", "GSTIN", "IFSC", "PAN", "PDF", "ID", "IBAN", "SWIFT", "API"}

EXTRACTED_FIELDS = (
    ("document_type", "Document Classification"),
    ("document_subtype", "Document Subtype"),
    ("document_title", "Document Title"),
    ("registration_form", "Registration Form"),
    ("legal_name", "Registered Legal Name"),
    ("trade_name", "Trade Name"),
    ("gstin", "GSTIN"),
    ("bank_name", "Bank Name"),
    ("account_holder", "Account Holder"),
    ("account_number", "Account Number"),
    ("ifsc", "IFSC Code"),
    ("classification_evidence", "Classification Evidence"),
)


def as_record(record) -> dict:
    """Accept sqlite3.Row, a dict, or any mapping-like result."""
    return dict(record)


def field(record, *names, default=""):
    d = as_record(record)
    for name in names:
        if name in d and d[name] is not None:
            return d[name]
    return default


def application_id(value):
    return f"VND-{int(value):06d}"


def pretty_code(raw):
    raw = str(raw or "").strip()
    if not raw:
        return "Activity"
    key = raw.upper()
    if key in EVENT_LABELS:
        return EVENT_LABELS[key]
    if key.startswith("REQUIRED_"):
        subject = key[len("REQUIRED_"):].lower()
        return f"{FIELD_LABELS.get(subject, subject.replace('_', ' ').title())} Provided"
    parts = re.split(r"[_\s\-]+", raw)
    return " ".join(p.upper() if p.upper() in ACRONYMS else p.capitalize() for p in parts if p)


def pretty_message(message):
    """Present readable wording without changing the underlying logged evidence."""
    msg = str(message or "").strip()
    if not msg:
        return "No additional details recorded."
    msg = msg.replace(
        "GST certificate upload contains an educational GSTIN infographic, not registration evidence.",
        "The uploaded GST certificate is invalid.",
    )
    msg = re.sub(r"(?<!\w)\d(?:[ -]?\d){8,}(?!\w)", "[number hidden]", msg)
    # Match complete human labels and raw keys in one pass: never expand the
    # word email inside Business Email, or ifsc inside IFSC Code, a second time.
    labels = {name.casefold(): label for name, label in FIELD_LABELS.items()}
    labels.update({label.casefold(): label for label in FIELD_LABELS.values()})
    alternatives = "|".join(re.escape(name) for name in sorted(labels, key=len, reverse=True))
    msg = re.sub(rf"(?<![a-zA-Z0-9_])(?:{alternatives})(?![a-zA-Z0-9_])",
                 lambda match: labels[match.group().casefold()], msg, flags=re.I)
    for name, label in (("GST_CERTIFICATE", "GST Registration Certificate"), ("BANK_PROOF", "Bank Account Proof")):
        msg = msg.replace(name, label)
    return msg


def pretty_status(status):
    return {
        "APPROVED": "Approved", "PENDING": "Pending", "REJECTED": "Rejected",
        "PROCESSING": "Processing", "SUBMITTED": "Received", "PASS": "Passed",
        "SUCCESS": "Completed", "FAIL": "Failed", "FAILED": "Failed",
        "ERROR": "Error", "WARNING": "Warning",
        "VERIFIED": "Verified", "NOT_VERIFIED": "Not Verified",
        "VERIFICATION_FAILED": "Verification Failed", "NOT_CONFIGURED": "Not Configured",
        "ACCEPTED": "Accepted",
    }.get(str(status or "").upper(), pretty_code(status))


def decision_message(reason):
    """Keep the result concise; detailed policy wording stays in checks/audit."""
    message = str(reason or "").strip()
    if message == (
        "All configured synthetic demonstration consistency checks passed. "
        "Document authenticity remains NOT_VERIFIED unless separately recorded; "
        "no independent government or banking verification is claimed."
    ):
        return "All required information and document consistency checks passed."
    return pretty_message(message)


def category(code):
    c = str(code or "").upper()
    if c.startswith("REQUIRED_"):
        return "Required Information"
    if "DUPLICATE" in c:
        return "Duplicate Registration"
    if "GST" in c or "TAX" in c:
        return "Tax Verification"
    if "BANK" in c or "IFSC" in c:
        return "Banking Information"
    if "DOCUMENT" in c or "EXTRACTION" in c:
        return "Document Analysis"
    if "DECISION" in c:
        return "Decision"
    return "Application Processing"


def mask_account(value):
    raw = str(value or "").strip()
    return f"•••• {raw[-4:]}" if raw else "Not found"


def normalize_events(events):
    """Present process logs as business-readable records without mutating the DB."""
    items = []
    for event in events or []:
        code = field(event, "stage", "event_type", "event_code", "code", "event_name")
        result = field(event, "outcome", "status", "result")
        when = field(event, "created_at", "timestamp", "event_time")
        detail = field(event, "message", "description", "details")
        items.append({
            "Step": pretty_code(code),
            "Category": category(code),
            "Result": pretty_status(result),
            "Details": pretty_message(detail),
            "Recorded At": str(when or "—"),
            "Revision": field(event, "revision", default=1),
            "Recorded By": field(event, "actor", default="system"),
            "_code": str(code or ""),
            "_result": str(result or ""),
        })
    return items


def render_table(rows, columns, *, height=320, empty="No records to display."):
    if not rows:
        st.info(empty)
        return
    df = pd.DataFrame(rows).reindex(columns=columns)
    st.dataframe(df, hide_index=True, width="stretch", height=height)


def activity_table(events, *, limit=8):
    """Newest activity first. Audit events are not abbreviated in storage."""
    normalized = normalize_events(events)
    if limit is not None:
        legacy_mail_events = {"EMAIL_NOTIFICATION", "EMAIL_DELIVERY_FAILURE", "COMMUNICATION_RECEIPT"}
        normalized = [event for event in normalized if event["_code"] not in legacy_mail_events]
    recent = list(reversed(normalized))
    if limit:
        recent = recent[:limit]
    render_table(
        recent,
        (["Recorded At", "Revision", "Step", "Result", "Recorded By", "Details"] if limit is None else
         ["Recorded At", "Step", "Result", "Details"]),
        height=min(380, 38 * (len(recent) + 1) + 8),
        empty="No activity has been recorded for this application.",
    )


def checks_table(checks):
    rows = []
    for check in checks or []:
        code = field(check, "code", "stage", "event_type")
        if code == "COMMUNICATION_RECEIPT":
            continue  # Obsolete historical check; retained in storage/audit only.
        outcome = field(check, "outcome", "status", "result")
        rows.append({
            "Verification Check": pretty_code(code),
            "Category": category(code),
            "Outcome": pretty_status(outcome),
            "Explanation": pretty_message(field(check, "message", "details")),
        })
    render_table(rows, ["Verification Check", "Category", "Outcome", "Explanation"], height=360,
                 empty="No verification checks are available.")


def extracted_table(data):
    if not isinstance(data, dict):
        st.warning("Stored extraction data is not readable.")
        return
    rows = []
    for key, label in EXTRACTED_FIELDS:
        val = data.get(key)
        if key == "account_number":
            val = mask_account(val)
        elif key in {"document_type", "document_subtype"} and val:
            val = pretty_code(val)
        if key != "account_number" and val:
            val = re.sub(r"\d(?:[ -]?\d){8,}", "[number hidden]", str(val))
        rows.append({"Field": label, "Extracted Information": str(val).strip() if val else "Not found"})
    render_table(rows, ["Field", "Extracted Information"], height=385)


def configure_theme():
    """All application CSS lives here; app.py contains no style or HTML."""
    st.html(r"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap');
      :root {
        --ink:#2C2038; --muted:#7C7189; --paper:#FDFBFE;
        --line:#EDE4F1; --orchid:#8856C6; --rose:#ED91B4;
        --purple:#342049; --lilac:#F3E8FA;
      }
      html,body,[class*="css"] {font-family:'DM Sans',system-ui,sans-serif;}
      .stApp {
        background: radial-gradient(ellipse 70% 28% at 75% 0%,#F8EBFC 0%,transparent 75%),
                    linear-gradient(145deg,#FFFBFC 0%,#FCFAFF 55%,#F8F2FA 100%);
        color:var(--ink);
      }
      .block-container {max-width:1490px;padding:1.6rem 2.7rem 4rem;}
      h1,h2,h3,h4{font-family:'Outfit','DM Sans',sans-serif;color:var(--ink);letter-spacing:-.035em}
      [data-testid="stHeader"]{background:transparent}
      [data-testid="stSidebar"] {
        background:linear-gradient(169deg,#2B193C 0%,#37204C 65%,#48305B 100%);
        border-right:1px solid #573E6D;
      }
      [data-testid="stSidebar"]>div{padding-top:1.2rem}
      [data-testid="stSidebar"] hr{border-color:#6C517C;opacity:.4}
      [data-testid="stSidebar"] .stCaptionContainer {color:#D8C9E3}
      [data-testid="stSidebar"] .stButton button {
         color:#E6D9EF; background:transparent;border:1px solid transparent;
         min-height:46px;border-radius:11px;text-align:left;justify-content:flex-start;
         font-weight:600;padding-left:17px;letter-spacing:.005em;
      }
      [data-testid="stSidebar"] .stButton button:hover{
        background:#57396E;border-color:#6F507F;color:#FFFFFF;
      }
      [data-testid="stSidebar"] .stButton button[kind="primary"]{
        background:#F6D5ED;color:#38214F;border-color:#F6D5ED;font-weight:800;
        box-shadow:0 4px 18px rgba(236,143,193,.14);
      }
      .v-brand{padding:6px 2px 28px}
      .v-logo{display:flex;align-items:center;gap:11px}
      .v-logo-icon{display:flex;align-items:center;justify-content:center;
        width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,#F8B7D8,#D9B4FF);
        color:#3D2459;font-family:Outfit;font-size:25px;font-weight:800}
      .v-wordmark{color:white;font-family:Outfit;font-size:25px;font-weight:800;letter-spacing:-1.25px}
      .v-brand-caption{font-size:10px;font-weight:700;letter-spacing:2px;color:#C9B2D7;margin-top:13px}
      .v-nav-caption{font-size:10px;font-weight:800;letter-spacing:2px;color:#A991BA;margin-bottom:12px}
      .v-sidebar-note{color:#D4C5E0;font-size:12px;line-height:1.8;padding:22px 2px}
      .v-badge-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#F5B7D5;margin-right:7px}
      .v-eyebrow{color:#A25DBC;font-size:11px;letter-spacing:2px;font-weight:800;text-transform:uppercase;margin:4px 0 10px}
      .v-h1{font-family:Outfit,sans-serif;font-size:clamp(31px,3vw,44px);font-weight:800;
        color:#2C2038;letter-spacing:-1.8px;line-height:1.12;margin:0 0 10px}
      .v-deck{font-size:14px;color:#85798B;line-height:1.7;margin:0 0 22px}
      .v-hero{
        isolation:isolate;position:relative;overflow:hidden;border-radius:23px;
        background:radial-gradient(ellipse 40% 90% at 95% 12%,#EAB7E5 0%,transparent 70%),
                   radial-gradient(ellipse 65% 90% at 6% 100%,#FFD0DC 0%,transparent 66%),
                   radial-gradient(ellipse 50% 95% at 65% 10%,#F7B8C7 0%,transparent 75%),
                   linear-gradient(110deg,#F4D5F5 0%,#F5BBD3 45%,#E9D1FE 100%);
        border:1px solid #EEC8ED;padding:30px 36px 31px;margin:0 0 24px;
        box-shadow:0 10px 36px rgba(165,107,163,.08);
      }
      .v-hero::before{content:'';position:absolute;inset:-25% -7% auto auto;width:55%;height:155%;
        background:repeating-radial-gradient(ellipse at 30% 40%,transparent 0px,transparent 26px,
        rgba(255,255,255,.17) 27px,rgba(255,255,255,.17) 28px,transparent 29px,transparent 54px);
        transform:rotate(-14deg);z-index:-1;pointer-events:none}
      .v-hero-tag{display:inline-flex;align-items:center;background:rgba(255,255,255,.56);
        padding:8px 12px;border:1px solid rgba(255,255,255,.67);border-radius:100px;
        color:#5A336B;font-size:10px;font-weight:800;letter-spacing:1.3px;margin-bottom:16px}
      .v-hero-title{font-family:Outfit,sans-serif;color:#3E1C57;font-size:clamp(31px,3.7vw,52px);
        letter-spacing:-2.5px;line-height:1.06;font-weight:800;max-width:850px;margin:0 0 11px}
      .v-hero-title span{color:#9D497E}
      .v-hero-copy{font-size:13px;line-height:1.65;color:#694E76;max-width:700px;margin:0}
      .v-hero-steps{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
      .v-step{padding:6px 11px;font-size:10px;font-weight:800;letter-spacing:1px;border-radius:7px;
        color:#6B4B78;border:1px solid rgba(255,255,255,.65);background:rgba(255,255,255,.4)}
      .v-section{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:23px 0 12px}
      .v-section-title{font-family:Outfit,sans-serif;color:#2B2037;font-size:20px;font-weight:750;letter-spacing:-.55px}
      .v-section-sub{font-size:12px;color:#9A8E9F;margin-top:3px}
      .v-card{background:#FFFFFF;border:1px solid #EDE4F1;border-radius:17px;padding:19px 21px;
        box-shadow:0 5px 26px rgba(76,40,90,.035);min-height:137px}
      .v-card-head{display:flex;align-items:center;justify-content:space-between}
      .v-card-label{font-size:12px;font-weight:700;color:#8B7B96}
      .v-card-icon{border-radius:10px;width:31px;height:31px;background:var(--tint);
        color:var(--accent);font-size:16px;display:flex;align-items:center;justify-content:center;font-weight:800}
      .v-card-value{font-family:Outfit,sans-serif;font-size:38px;font-weight:800;
        line-height:1.3;letter-spacing:-1.7px;color:#33223E;margin:8px 0 0}
      .v-card-note{color:#A89BAE;font-size:11px;margin-top:2px}
      .v-pill{display:inline-flex;align-items:center;gap:6px;border-radius:100px;padding:7px 12px;
        font-weight:800;font-size:11px}
      .v-pill::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor}
      .v-pill.approved{background:#E4F7EC;color:#248453}
      .v-pill.pending{background:#FFF0D9;color:#A26B22}
      .v-pill.rejected{background:#FCE3EA;color:#BE4261}
      .v-pill.received{background:#EEE4FA;color:#7A53B3}
      .v-minicallout{padding:17px 20px;border:1px solid #EADDF0;background:#FDF6FD;
        border-radius:14px;color:#70587E;font-size:13px;line-height:1.6}
      [data-testid="stForm"]{background:#FFFFFF;border:1px solid #EDE4F1;
        border-radius:19px;padding:26px 28px;box-shadow:0 5px 24px rgba(76,40,90,.035)}
      [data-testid="stVerticalBlockBorderWrapper"]{border-radius:15px!important}
      [data-testid="stTextInput"] input{border-radius:10px}
      [data-testid="stFileUploader"]{border-radius:12px}
      .stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"],.stFormSubmitButton button[kind="primaryFormSubmit"]{
        background:#663A91;color:white;border:1px solid #663A91;border-radius:11px;font-weight:750;
        min-height:43px;box-shadow:none}
      .stButton button[kind="primary"]:hover,.stFormSubmitButton button[kind="primary"]:hover,.stFormSubmitButton button[kind="primaryFormSubmit"]:hover{
        background:#7F4BA7;border-color:#7F4BA7;color:white}
      [data-testid="stDataFrame"]{border:1px solid #EDE4F1;border-radius:12px;overflow:hidden}
      hr{border-color:#EAE0EC}
      @media(max-width:900px){.block-container{padding:1.3rem 1rem 3rem}
        .v-hero{padding:25px 22px}.v-hero-title{letter-spacing:-1.4px}}
    </style>
    """)


def sidebar():
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "Overview"
    with st.sidebar:
        st.html('''<div class="v-brand"><div class="v-logo"><div class="v-logo-icon">v</div>
             <div class="v-wordmark">vendence<span style="color:#F0B4D6">.</span></div></div>
             <div class="v-brand-caption">VENDOR ONBOARDING</div></div>
             <div class="v-nav-caption">WORKSPACE</div>''')
        for page, symbol in PAGES:
            if st.button(f"{symbol}   {page}", key=f"nav_{page}",
                         type="primary" if st.session_state.nav_page == page else "secondary",
                         width="stretch"):
                st.session_state.nav_page = page
                st.rerun()
        st.divider()
    return st.session_state.nav_page


def header(eyebrow, title, description):
    st.html(f'''<div class="v-eyebrow">{escape(eyebrow)}</div>
        <div class="v-h1">{escape(title)}</div><div class="v-deck">{escape(description)}</div>''')


def section(title, description=""):
    st.html(f'''<div class="v-section"><div><div class="v-section-title">{escape(title)}</div>
        <div class="v-section-sub">{escape(description)}</div></div></div>''')


def status_pill(status):
    state = str(status or "").upper()
    klass = "approved" if state == "APPROVED" else (
        "pending" if state == "PENDING" else ("rejected" if state == "REJECTED" else "received"))
    st.html(f'<span class="v-pill {klass}">{escape(pretty_status(state))}</span>')


def metric_cards(records):
    counts = {"APPROVED":0, "PENDING":0, "REJECTED":0}
    for item in records:
        s = str(field(item, "status")).upper()
        if s in counts:
            counts[s] += 1
    specs = [
        ("Applications", len(records), "Total vendor submissions", "◫", "#8455C9", "#F1E7FC"),
        ("Approved", counts["APPROVED"], "Completed decisions", "✓", "#2B976D", "#DEF6EC"),
        ("Pending", counts["PENDING"], "Outstanding applications", "!", "#D47B53", "#FDEADC"),
        ("Rejected", counts["REJECTED"], "Rejected submissions", "×", "#C95887", "#FCE5EF"),
    ]
    for col, (label, value, note, icon, color, tint) in zip(st.columns(4, gap="medium"), specs):
        with col:
            st.html(f'''<div class="v-card" style="--accent:{color};--tint:{tint}">
               <div class="v-card-head"><div class="v-card-label">{escape(label)}</div>
               <div class="v-card-icon">{escape(icon)}</div></div>
               <div class="v-card-value">{value}</div><div class="v-card-note">{escape(note)}</div></div>''')


def applications_table(records, *, limit=None, empty="No vendor applications yet."):
    selected = list(records)
    if limit is not None:
        selected = selected[:limit]
    rows = [{
        "Application ID": application_id(field(row, "submission_id")),
        "Vendor Name": field(row, "vendor_name") or "—",
        "Business Email": field(row, "email") or "—",
        "Submitted On": str(field(row, "created_at") or "—"),
        "Status": pretty_status(field(row, "status")),
    } for row in selected]
    render_table(rows, ["Application ID", "Vendor Name", "Business Email", "Submitted On", "Status"],
                 height=min(365, 38 * (len(rows) + 1) + 8), empty=empty)


def choose_application(records, key):
    if not records:
        st.info("No applications found.")
        return None
    ids = [int(field(r, "submission_id")) for r in records]
    # A new submission can put its own ID in session state to appear selected.
    preferred = st.session_state.get("focus_submission_id")
    if key in st.session_state and st.session_state[key] not in ids:
        # Send an explicit value update to the existing browser widget. Deleting
        # the key resets Python's selection but can leave the old ID on screen.
        st.session_state[key] = ids[0]
    index = ids.index(preferred) if preferred in ids and key not in st.session_state else 0
    selected = st.selectbox("Application", ids, index=index, format_func=application_id, key=key)
    return next(r for r in records if int(field(r, "submission_id")) == int(selected))


def open_application(submission_id, *, correction=False):
    """Apply explicit navigation before the target page's widgets are created."""
    st.session_state.focus_submission_id = submission_id
    st.session_state.verify_selected = submission_id
    st.session_state.nav_page = "Verification Center"
    if correction:
        st.session_state.open_correction_for = submission_id


def start_new_application():
    st.session_state.onboarding_form_version = st.session_state.get("onboarding_form_version", 1) + 1
    st.session_state.nav_page = "New Onboarding"
    st.session_state.pop("open_correction_for", None)
    st.session_state.pop("completed_onboarding_result", None)
    st.session_state.pop("show_onboarding_dialog", None)


def resume_application_panel(records):
    with st.expander("Continue an existing application"):
        st.caption("Enter your application ID to review the status, correct information, or replace documents.")
        with st.form("resume_application"):
            entered = st.text_input("Existing Application ID", placeholder="VND-000011")
            submitted = st.form_submit_button("Continue application  →", type="primary")
        if submitted:
            match = re.fullmatch(r"(?:VND-)?([0-9]{1,12})", entered.strip().upper())
            sid = int(match[1]) if match else None
            if sid not in {int(field(record, "submission_id")) for record in records}:
                st.warning("No matching application was found. Check the ID shown after submission.")
            else:
                open_application(sid, correction=True)
                st.rerun()


def overview(records, event_loader: Callable):
    left, right = st.columns([4.5, 1.4], gap="medium", vertical_alignment="center")
    with left:
        header("WORKSPACE  /  OVERVIEW", "Overview",
               "Applications, decisions and recent activity.")
    with right:
        st.button("＋  New application", type="primary", width="stretch", on_click=start_new_application)
    st.html('''<div class="v-hero">
      <div class="v-hero-title">Vendor onboarding<br><span>and verification.</span></div>
      <div class="v-hero-copy">Company details, tax documents and banking information.</div></div>''')
    metric_cards(records)
    section("Recent applications")
    applications_table(records, limit=6)
    section("Recent activity")
    if records:
        app_id = int(field(records[0], "submission_id"))
        st.caption(f"Application {application_id(app_id)}")
        activity_table(event_loader(app_id), limit=5)
    else:
        st.info("Activity will appear after the first submission.")


def onboarding_form(initial=None, correction=False, policy="strict", resumable_records=None):
    """Collect form data only; the caller owns persistence and verification.

    Correction widget keys include the application and revision, preventing
    stale uploads or edited fields from leaking between applications.
    """
    initial = as_record(initial) if initial is not None else {}
    suffix = (f"correction_{initial.get('submission_id', 'new')}_{initial.get('current_revision', 1)}"
              if correction else f"new_{st.session_state.get('onboarding_form_version', 1)}")
    def value(key):
        return str(initial.get(key) or "")
    def widget(key):
        return f"onboard_{suffix}_{key}"
    if correction:
        section("Correct and resubmit", "Changes are saved under the same application ID.")
    else:
        header("APPLICATIONS  /  NEW", "New application",
               "Enter company and bank details, then upload the required documents.")
        if resumable_records:
            resume_application_panel(resumable_records)
    with st.form(f"vendence_onboard_{suffix}", clear_on_submit=False):
        st.subheader("01  ·  Company details")
        st.caption("Use the legal name on the GST certificate.")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            vendor_name = st.text_input("Legal Company Name", value=value("vendor_name"), placeholder="Registered legal name", key=widget("vendor_name"))
            email = st.text_input("Business Email", value=value("email"), placeholder="finance@example.com", key=widget("email"))
        with c2:
            countries = ["India"]
            if value("country") and value("country") not in countries:
                countries.append(value("country"))
            country = st.selectbox("Country", countries, index=countries.index(value("country")) if value("country") in countries else 0, key=widget("country"))
            tax_id = st.text_input("GSTIN", value=value("tax_id"), placeholder="15-character registration number", key=widget("tax_id"))
        st.divider()
        st.subheader("02  ·  Banking information")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            banks = list(BANK_NAMES)
            if policy == "demo_consistency":
                banks.append("Example Demonstration Bank")
            saved_bank = value("bank_name")
            if saved_bank and saved_bank not in banks:
                banks.append(saved_bank)
            bank_name = st.selectbox(
                "Bank Name", banks, index=banks.index(saved_bank) if saved_bank else None,
                placeholder="Search or enter bank name", accept_new_options=True,
                help="If your bank is not listed, type its full name and press Enter.",
                key=widget("bank_name"),
            )
            bank_holder = st.text_input("Account Holder Name", value=value("bank_account_holder"), placeholder="As shown on banking proof", key=widget("bank_account_holder"))
        with c2:
            bank_number = st.text_input("Bank Account Number", value=value("bank_account_number"), type="password", placeholder="Account number", key=widget("bank_account_number"))
            ifsc = st.text_input("IFSC Code", value=value("ifsc_code"), placeholder="ABCD0001234", key=widget("ifsc_code"))
        st.divider()
        st.subheader("03  ·  Supporting documents")
        if correction:
            st.caption("Upload a replacement only for documents you want to change.")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            gst_document = st.file_uploader("GST Registration Certificate", type=["pdf", "png", "jpg", "jpeg"],
                                             max_upload_size=5, key=widget("gst_upload"))
        with c2:
            bank_document = st.file_uploader("Bank Account Proof", type=["pdf", "png", "jpg", "jpeg"],
                                              max_upload_size=5, key=widget("bank_upload"))
            st.caption("Upload a bank statement, account confirmation or cancelled cheque.")
        st.divider()
        correction_reason = ""
        if correction:
            correction_reason = st.text_area("What Did You Correct?", placeholder="Describe the correction. Do not include full bank details.", key=widget("correction_reason"))
        submitted = st.form_submit_button("Resubmit and verify  →" if correction else "Submit and verify  →", type="primary", width="stretch")
    if not submitted:
        return None
    st.session_state.correction_reason = correction_reason.strip()
    data = {
        "vendor_name": vendor_name.strip(), "email": email.strip(), "country": country,
        "tax_id": tax_id.strip().upper(), "bank_name": (bank_name or "").strip(),
        "bank_account_holder": bank_holder.strip(),
        "bank_account_number": bank_number.strip(), "ifsc_code": ifsc.strip().upper(),
    }
    return data, {"GST_CERTIFICATE": gst_document, "BANK_PROOF": bank_document}


def processing_result(submission_id, status, reason, checks):
    section("Verification result", f"Application {application_id(submission_id)}")
    with st.container(border=True):
        status_pill(status)
        st.write("")
        st.markdown("**Reason**")
        st.write(decision_message(reason))
    section("Verification checks")
    checks_table(checks)
    if status != "APPROVED":
        st.info("Open the application to correct the details or replace documents, then resubmit.")
    left, right = st.columns(2)
    with left:
        st.button("Open verification center  →", type="primary", on_click=open_application, args=(submission_id,))
    with right:
        st.button("Start another application", on_click=start_new_application)


@st.dialog("Application status", width="large")
def submission_status_dialog(submission_id, status, reason, checks):
    """Present the actual saved workflow result immediately after submission."""
    st.caption(application_id(submission_id))
    status_pill(status)
    st.markdown("**Decision**")
    st.write(decision_message(reason))
    if status in {"PENDING", "REJECTED"}:
        st.info("Select View application to make corrections and resubmit.")
    with st.expander("View checks"):
        checks_table(checks)
    if st.button("View application", type="primary", key="view_submitted_application"):
        open_application(submission_id, correction=status in {"PENDING", "REJECTED"})
        st.rerun()


def _file_candidates(document, root: Path):
    """Only a recorded path inside this workspace's upload store is previewable."""
    root = Path(root)
    uploads_root = (root / "uploads").resolve()
    for key in ("file_path", "storage_path", "stored_path", "saved_path"):
        raw = str(field(document, key) or "").strip()
        if not raw:
            continue
        path = Path(raw)
        try:
            resolved = (path if path.is_absolute() else root / path).resolve()
            if resolved.is_relative_to(uploads_root) and resolved.is_file():
                yield resolved
        except (OSError, ValueError, RuntimeError):
            continue


def _resolve_preview(document, root: Path):
    return next(_file_candidates(document, root), None)


def preview_document(document, root: Path, *, key_suffix=""):
    """View real uploaded bytes; never guess another application's filename."""
    path = _resolve_preview(document, root)
    if path is None:
        st.info("Original document unavailable: the saved file is missing or its path is outside the document store.")
        return
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            st.info("This stored document exceeds the preview size limit.")
            return
        data = path.read_bytes()
    except OSError:
        st.warning("The saved document could not be read. Review or replace the original file.")
        return
    mime = str(field(document, "mime_type") or "")
    suffix = path.suffix.lower()
    if mime in {"image/png", "image/jpeg"} or suffix in {".png", ".jpg", ".jpeg"}:
        try:
            st.image(data, caption="Original uploaded document", width="stretch")
        except Exception:
            st.warning("The saved image could not be displayed.")
    elif mime == "application/pdf" or suffix == ".pdf":
        try:
            st.pdf(data, height=430, key=f"preview_pdf_{field(document, 'document_id', default=path.name)}_{key_suffix}",
                   alt="Original uploaded supporting document")
        except Exception:
            st.info("The original PDF is available below when inline viewing is unavailable.")
        st.download_button("Download Original PDF", data, file_name=path.name, mime="application/pdf",
                           key=f"dl_pdf_{field(document, 'document_id', 'id', default=path.name)}_{key_suffix}")
    else:
        st.info("This file format cannot be displayed inline.")


def authenticity_details(document, authenticity_loader=None):
    document_id = field(document, "document_id", "id")
    record = as_record(authenticity_loader(document_id) or {}) if authenticity_loader and document_id is not None else {}
    state = str(record.get("state") or "NOT_VERIFIED")
    st.markdown(f"**Document Authenticity: {pretty_status(state)}**")
    if state == "VERIFIED":
        st.caption("Review details and evidence references are shown below.")
    elif state == "VERIFICATION_FAILED":
        st.warning("Independent verification failed. Review or replace this document.")
    else:
        st.caption("Document matching does not confirm authenticity.")
    if record.get("method") or record.get("reviewer") or record.get("evidence_reference"):
        rows = [{"Method": pretty_code(record.get("method")), "Reviewer": record.get("reviewer") or "—",
                 "Evidence Reference": record.get("evidence_reference") or "—",
                 "Recorded At": record.get("created_at") or record.get("verified_at") or "—"}]
        render_table(rows, ["Method", "Reviewer", "Evidence Reference", "Recorded At"], height=100)


def verification(records, event_loader: Callable, document_loader: Callable, root: Path, *,
                 check_loader=None, authenticity_loader=None, history_loader=None,
                 revision_loader=None):
    header("APPLICATIONS  /  VERIFICATION", "Verification Center",
           "Review documents, verification results and application history.")
    selected = choose_application(records, "verify_selected")
    if selected is None:
        return None
    submission_id = int(field(selected, "submission_id"))
    revision = int(field(selected, "current_revision", default=1))
    with st.container(border=True):
        top1, top2 = st.columns([4, 1], vertical_alignment="center")
        with top1:
            st.subheader(str(field(selected, 'vendor_name') or 'Unnamed vendor'))
            st.caption(f"{application_id(submission_id)} · Revision {revision} · {field(selected, 'email') or 'No email'}")
        with top2:
            status_pill(field(selected, "status"))
        st.markdown("**Decision explanation**")
        st.write(decision_message(field(selected, "decision_reason") or "The decision is not yet recorded."))
    events = list(event_loader(submission_id) or [])
    current_events = [event for event in events if int(field(event, "revision", default=revision)) == revision]
    # Persisted check records are the source of current results. Audit events
    # include technical stages and earlier revisions, so must not substitute.
    check_rows = list(check_loader(submission_id) or []) if check_loader else []
    docs = list(document_loader(submission_id) or [])
    left, right = st.columns([1.05, 1.35], gap="large")
    with left:
        section("Uploaded documents")
        if not docs:
            st.info("No uploaded documents are available for this application.")
        else:
            chosen = st.selectbox("Document", list(range(len(docs))),
                                  format_func=lambda i: f"{pretty_code(field(docs[i], 'document_type'))} · "
                                                       f"{field(docs[i], 'original_filename', 'file_name', 'filename') or 'Uploaded file'}",
                                  key=f"doc_select_{submission_id}_{revision}")
            doc = as_record(docs[chosen])
            with st.container(border=True):
                authenticity_details(doc, authenticity_loader)
                preview_document(doc, root)
            section("Extracted information", "Details read from this document.")
            raw = field(doc, "extracted_data")
            if raw:
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else dict(raw)
                    extracted_table(parsed)
                except (ValueError, TypeError):
                    st.warning("Saved AI extraction details could not be parsed.")
            else:
                st.info("No AI extraction has been saved for this document.")
        if history_loader:
            with st.expander("Earlier Documents and Replacements"):
                historical = list(history_loader(submission_id) or [])
                rows = [{"Revision": field(row, "revision", default=1),
                         "Document": pretty_code(field(row, "document_type")),
                         "Uploaded File": field(row, "original_filename", "file_name", default="—"),
                         "Saved At": field(row, "uploaded_at", "created_at") or "—"} for row in historical]
                render_table(rows, ["Revision", "Document", "Uploaded File", "Saved At"], height=220,
                             empty="No document history has been recorded.")
                if historical:
                    index = st.selectbox("Historical Document", list(range(len(historical))),
                                         format_func=lambda i: f"Revision {field(historical[i], 'revision', default=1)} · {pretty_code(field(historical[i], 'document_type'))} · Document {field(historical[i], 'document_id')}",
                                         key=f"historical_doc_{submission_id}_{revision}")
                    if st.checkbox("Show Original Historical Document", key=f"show_history_preview_{submission_id}_{revision}"):
                        preview_document(historical[index], root, key_suffix="historical")
    with right:
        section("Verification checks", f"Revision {revision}")
        checks_table(check_rows)
        section("Processing activity")
        activity_table(current_events, limit=7)
        with st.expander("View Complete Audit History"):
            activity_table(events, limit=None)
        if revision_loader:
            with st.expander("Application Revisions"):
                rows = [{"Revision": field(row, "revision"), "Correction Summary": field(row, "correction_reason") or "Initial submission",
                         "Recorded At": field(row, "created_at") or "—"} for row in revision_loader(submission_id) or []]
                render_table(rows, ["Revision", "Correction Summary", "Recorded At"], height=220)
    return submission_id


def reviewer_panel(submission, documents, auth_loader=None):
    """Return a requested attestation. Caller must enforce reviewer authorization."""
    documents = list(documents or [])
    if not documents:
        st.info("Upload supporting documents before recording a verification review.")
        return None
    sid = int(field(submission, "submission_id"))
    revision = int(field(submission, "current_revision", default=1))
    section("Authorized Document Review", "Record the method, independent evidence, and scope. The business rules will recheck the application.")
    index = st.selectbox("Document to Review", list(range(len(documents))),
                         format_func=lambda i: pretty_code(field(documents[i], "document_type")), key=f"review_document_{sid}_{revision}")
    document = as_record(documents[index])
    doc_id = int(field(document, "document_id", "id"))
    authenticity_details(document, auth_loader)
    method_labels = {
        "GST_PORTAL_AND_ORIGINAL": "GST Portal Record and Original Certificate",
        "TRUSTED_DIGITAL_SIGNATURE": "Trusted Digital Signature Verification",
        "BANK_CONFIRMATION": "Independent Bank Confirmation",
        "AUTHORIZED_REVIEW": "Authorized Review with Documented Independent Evidence",
    }
    methods = (["GST_PORTAL_AND_ORIGINAL", "TRUSTED_DIGITAL_SIGNATURE", "AUTHORIZED_REVIEW"]
               if field(document, "document_type") == "GST_CERTIFICATE" else ["BANK_CONFIRMATION", "AUTHORIZED_REVIEW"])
    with st.form(f"auth_review_{sid}_{revision}_{doc_id}"):
        state = st.selectbox("Verification State", ["NOT_VERIFIED", "VERIFIED", "VERIFICATION_FAILED"], format_func=pretty_status)
        method = st.selectbox("Verification Method", methods, format_func=lambda item: method_labels[item])
        reviewer = st.text_input("Reviewer Name", placeholder="Authorized reviewer")
        reference = st.text_input("Independent Evidence Reference", placeholder="Controlled evidence reference or verification case ID")
        notes = st.text_area("Verification Scope and Notes", placeholder="Record what was checked and any limitations. Omit full bank account numbers and credentials.")
        confirmed = st.checkbox("I performed independent checks; AI appearance alone is insufficient.")
        st.caption("A taxpayer-record match alone does not prove an uploaded certificate is genuine. Confirm the original document or a trustworthy verification process and document its scope.")
        submitted = st.form_submit_button("Record Verification Review", type="primary")
    if not submitted:
        return None
    if not reviewer.strip():
        st.warning("Enter the authorized reviewer's name for every recorded review.")
        return None
    if state == "VERIFIED" and (not confirmed or not reviewer.strip() or not reference.strip()):
        st.warning("Verified status requires completed independent checks, an authorized reviewer name, and an evidence reference.")
        return None
    return {"action": "record_authenticity", "document_id": doc_id, "state": state, "method": method,
            "reviewer": reviewer.strip(), "evidence_reference": reference.strip(), "notes": notes.strip(),
            "independent_checks_confirmed": confirmed}


def registry(records, event_loader: Callable):
    header("APPLICATIONS  /  DIRECTORY", "Vendor Registry",
           "Search applications and review their status.")
    metric_cards(records)
    section("All applications")
    a, b = st.columns([2.2, 1], gap="medium")
    with a:
        query = st.text_input("Search", placeholder="Vendor name, email, GSTIN, or application ID")
    with b:
        state = st.selectbox("Status", ["All statuses", "Approved", "Pending", "Rejected"])
    filtered = []
    for row in records:
        searchable = " ".join([
            str(field(row, "vendor_name")), str(field(row, "email")),
            str(field(row, "tax_id")), application_id(field(row, "submission_id")),
        ]).lower()
        if query.strip().lower() in searchable and (state == "All statuses" or pretty_status(field(row, "status")) == state):
            filtered.append(row)
    applications_table(filtered, empty="No applications match these filters.")
    st.caption(f"Showing {len(filtered)} of {len(records)} applications.")
    if not filtered:
        return
    section("Application details")
    selected = choose_application(filtered, "registry_selected")
    if selected is None:
        return
    sid = int(field(selected, "submission_id"))
    with st.container(border=True):
        a, b = st.columns(2)
        with a:
            st.markdown(f"**{application_id(sid)}**")
            st.write(field(selected, "vendor_name") or "Unnamed vendor")
            st.caption(field(selected, "email") or "No contact email")
        with b:
            status_pill(field(selected, "status"))
            st.caption(f"Submitted: {field(selected, 'created_at') or 'Unknown'}")
        st.divider()
        st.markdown("**Decision explanation**")
        st.write(decision_message(field(selected, "decision_reason") or "No decision has been recorded."))
    with st.expander("Complete audit history"):
        activity_table(event_loader(sid), limit=None)
