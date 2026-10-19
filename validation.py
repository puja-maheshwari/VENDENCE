"""Deterministic, fail-closed onboarding checks.

Format, AI document classification, and independent verification are separate.
No AI output is permitted to choose a final business decision.
"""
from __future__ import annotations

from collections.abc import Mapping
from difflib import SequenceMatcher
from io import BytesIO
import re
import unicodedata
import warnings

MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_PAGES = 30
MAX_IMAGE_PIXELS = 20_000_000
REQUIRED_DOCUMENT_TYPES = ("GST_CERTIFICATE", "BANK_PROOF")
APPROVAL_POLICIES = frozenset({"strict", "demo_consistency"})
AUTHENTICITY_STATES = frozenset({"VERIFIED", "NOT_VERIFIED", "VERIFICATION_FAILED"})
# Current NIC state-code table; 25 and 28 are retired codes and require review.
# https://docs.ewaybillgst.gov.in/apidocs/state-code.html
GST_STATE_CODES = frozenset(f"{code:02d}" for code in range(1, 39) if code not in {25, 28}) | {"97", "99"}
GSTIN_PATTERN = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[A-Z0-9]"
GST_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REQUIRED_FIELDS = {
    "vendor_name": "Legal company name", "email": "Business email",
    "country": "Country", "tax_id": "GSTIN", "bank_name": "Bank name",
    "bank_account_holder": "Bank account holder",
    "bank_account_number": "Bank account number", "ifsc_code": "IFSC code",
}
DOCUMENT_COMPARISONS = {
    "GST_CERTIFICATE": (("vendor_name", "legal_name", "name"), ("tax_id", "gstin", "code")),
    "BANK_PROOF": (
        ("bank_account_holder", "account_holder", "name"),
        ("bank_account_number", "account_number", "account"),
        ("ifsc_code", "ifsc", "code"), ("bank_name", "bank_name", "bank"),
    ),
}


def _text(value):
    return value if isinstance(value, str) else ""


def make_check(code, outcome, message):
    return {"code": code, "outcome": outcome, "message": message}


def normalize_name(value):
    """Permit punctuation, case and Pvt/Ltd variants, never fuzzy name matches."""
    value = unicodedata.normalize("NFKC", _text(value)).upper().strip()
    value = value.replace("&", " AND ")
    value = re.sub(r"[^\w ]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\bPVT\b", "PRIVATE", value)
    value = re.sub(r"\bLTD\b", "LIMITED", value)
    return " ".join(value.split())


def normalize_account(value):
    return re.sub(r"[\s-]", "", _text(value))


def normalize_bank_name(value):
    """Normalize bank legal suffix spelling without fuzzy identity matching."""
    return re.sub(r"\s+LIMITED$", "", normalize_name(value)).strip()


def normalize_code(value):
    """Identifier canonicalization shared by format checks and persistence."""
    return re.sub(r"\s", "", _text(value)).upper()


def same_value(expected, actual, mode="text"):
    normalizer = {"name": normalize_name, "bank": normalize_bank_name,
                  "account": normalize_account, "code": normalize_code}.get(mode)
    if normalizer:
        expected, actual = normalizer(expected), normalizer(actual)
    else:
        expected, actual = _text(expected).strip().casefold(), _text(actual).strip().casefold()
    return bool(expected and actual and expected == actual)


def holder_names_clearly_differ(expected, actual):
    """Reject distinct readable names; possible variations require review.

    Similarity only keeps an uncertain mismatch Pending. It never makes a
    match pass or establishes the identity/authenticity of a bank account.
    """
    suffixes = {"PRIVATE", "LIMITED", "LLP", "LLC", "INC", "COMPANY", "CO", "CORPORATION"}
    names = []
    for raw in (expected, actual):
        text = _text(raw).strip()
        normalized = normalize_name(text)
        if (not normalized or re.search(r"[0-9*?_]", text) or normalized in {
                "UNKNOWN", "UNREADABLE", "UNCLEAR", "NOT AVAILABLE", "NOT FOUND", "NA", "N A", "NONE"}):
            return False
        tokens = [token for token in normalized.split() if token not in suffixes]
        if not tokens or any(len(token) == 1 for token in tokens):
            return False
        names.append(tokens)
    left, right = names
    if set(left) & set(right):
        return False
    a, b = "".join(left), "".join(right)
    if a in b or b in a or a == "".join(token[0] for token in right) or b == "".join(token[0] for token in left):
        return False
    return SequenceMatcher(None, a, b).ratio() < 0.75


def gstin_check_digit(first_fourteen):
    """Compute the GSTIN Luhn mod-36 check character; not a registry lookup."""
    value = normalize_code(first_fourteen)
    if len(value) != 14 or any(char not in GST_ALPHABET for char in value):
        raise ValueError("GSTIN checksum requires fourteen alphanumeric characters.")
    total, factor = 0, 2
    for char in reversed(value):
        product = GST_ALPHABET.index(char) * factor
        total += product // 36 + product % 36
        factor = 1 if factor == 2 else 2
    return GST_ALPHABET[(36 - total % 36) % 36]


def valid_gstin_checksum(value):
    value = normalize_code(value)
    return bool(len(value) == 15 and re.fullmatch(GSTIN_PATTERN, value)
                and gstin_check_digit(value[:14]) == value[-1])


def check_required_fields(data):
    return [make_check(f"REQUIRED_{field.upper()}",
                       "PASS" if _text(data.get(field)).strip() else "PENDING",
                       f"{label} provided." if _text(data.get(field)).strip()
                       else f"Missing mandatory field: {label}.")
            for field, label in REQUIRED_FIELDS.items()]


def missing_submission_requirements(data, uploads, existing_document_types=()):
    """Form completeness only; backend verification still validates all evidence."""
    fields = [label for key, label in REQUIRED_FIELDS.items() if not _text(data.get(key)).strip()]
    labels = {"GST_CERTIFICATE": "GST registration certificate", "BANK_PROOF": "Bank account proof"}
    documents = [labels[kind] for kind in REQUIRED_DOCUMENT_TYPES
                 if uploads.get(kind) is None and kind not in existing_document_types]
    return fields, documents


def summarize_check_issues(checks):
    """Summarize causes once while retaining every individual check in the audit."""
    valid = [c for c in checks if isinstance(c, Mapping) and isinstance(c.get("code"), str)]
    outcomes = {c["code"]: c.get("outcome") for c in valid}
    missing = [key for key in REQUIRED_FIELDS if outcomes.get(f"REQUIRED_{key.upper()}") == "PENDING"]
    messages = []
    # Explicit rejection reasons lead the explanation.
    messages.extend(c["message"].strip() for c in valid
                    if c.get("outcome") == "REJECTED" and isinstance(c.get("message"), str) and c["message"].strip())
    if missing:
        messages.append("Missing required information: " + ", ".join(REQUIRED_FIELDS[key] for key in missing) + ".")
    dependencies = {"EMAIL_FORMAT": ("email",), "COUNTRY_SCOPE": ("country",),
                    "GSTIN_FORMAT": ("tax_id",), "IFSC_FORMAT": ("ifsc_code",),
                    "ACCOUNT_NUMBER_FORMAT": ("bank_account_number",),
                    "SUBMITTED_BANK_HOLDER": ("vendor_name", "bank_account_holder")}
    for check in valid:
        code, outcome, message = check["code"], check.get("outcome"), check.get("message")
        if outcome in ("PASS", "REJECTED") or not isinstance(message, str) or not message.strip():
            continue
        if outcome == "PENDING":
            if code == "SUBMITTED_BANK_HOLDER" and outcomes.get("BANK_PROOF_BANK_ACCOUNT_HOLDER_MATCH") == "REJECTED":
                continue  # The bank-document contradiction is the specific cause.
            if code in {f"REQUIRED_{key.upper()}" for key in missing}:
                continue
            if any(key in missing for key in dependencies.get(code, ())):
                continue
            if code in {"GSTIN_STATE_CODE", "GSTIN_CHECKSUM"} and outcomes.get("GSTIN_FORMAT") != "PASS":
                continue
            dependent = False
            for kind in REQUIRED_DOCUMENT_TYPES:
                if not code.startswith(kind + "_") or code == kind + "_UPLOAD":
                    continue
                if outcomes.get(kind + "_UPLOAD") not in (None, "PASS"):
                    # Preserve a recorded authenticity failure even when the upload is unavailable.
                    if code.endswith("_AUTHENTICITY") and not message.startswith("NOT_VERIFIED"):
                        continue
                    dependent = True
                elif code.endswith("_MATCH") and outcomes.get(kind + "_IDENTITY") not in (None, "PASS"):
                    dependent = True
            if dependent:
                continue
        messages.append(message.strip())
    return list(dict.fromkeys(messages))


def valid_email(value):
    """Conservative ASCII mailbox syntax; does not verify mailbox existence."""
    email = _text(value).strip()
    if len(email) > 254 or email.count("@") != 1:
        return False
    local, domain = email.rsplit("@", 1)
    if not 1 <= len(local) <= 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        return False
    labels = domain.split(".")
    return bool(len(labels) >= 2 and re.fullmatch(r"[A-Za-z]{2,63}", labels[-1]) and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels))


def check_field_formats(data):
    """Always emit every configured format check, including missing inputs."""
    email = _text(data.get("email")).strip()
    email_valid = valid_email(email)
    gstin = normalize_code(data.get("tax_id"))
    gst_format = bool(re.fullmatch(GSTIN_PATTERN, gstin))
    state_valid = gst_format and gstin[:2] in GST_STATE_CODES
    checksum_valid = gst_format and valid_gstin_checksum(gstin)
    ifsc_valid = bool(re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", normalize_code(data.get("ifsc_code"))))
    account_valid = bool(re.fullmatch(r"[0-9]{9,18}", normalize_account(data.get("bank_account_number"))))
    country_valid = _text(data.get("country")).strip().casefold() == "india"
    holder_valid = same_value(data.get("vendor_name"), data.get("bank_account_holder"), "name")
    specifications = [
        ("EMAIL_FORMAT", email_valid, "Business email format is valid.",
         "Business email format is invalid. Correct it and resubmit." if email else "Business email is missing."),
        ("COUNTRY_SCOPE", country_valid, "Country is supported by the Indian GST business policy.", "Current policy supports Indian GST-registered businesses only."),
        ("GSTIN_FORMAT", gst_format, "GSTIN structure is valid; taxpayer existence has not been verified.",
         "GSTIN structure is invalid. Enter a valid 15-character GSTIN and resubmit." if gstin else "GSTIN is missing."),
        ("GSTIN_STATE_CODE", state_valid, "GSTIN uses a currently configured state code.",
         "GSTIN state code is invalid or retired under the India policy. Correct it and resubmit." if gst_format else
         "GSTIN state code could not be checked until a valid GSTIN is provided."),
        ("GSTIN_CHECKSUM", checksum_valid, "GSTIN checksum is valid; this does not prove registration or authenticity.",
         "GSTIN checksum is invalid. Check the registration number and resubmit." if gst_format else
         "GSTIN checksum could not be checked until a valid GSTIN is provided."),
        ("IFSC_FORMAT", ifsc_valid, "IFSC structure is valid; branch existence has not been verified.", "IFSC must contain four letters, zero, and six alphanumeric characters."),
        ("ACCOUNT_NUMBER_FORMAT", account_valid, "Account number satisfies the configured 9–18 digit format; account existence is unverified.", "Account number must contain 9–18 digits under the demonstration format policy."),
        ("SUBMITTED_BANK_HOLDER", holder_valid, "Submitted account holder matches the legal entity.", "Submitted account holder differs from the legal company name or is missing. Human review required."),
    ]
    rejected = set()
    for code, field, valid in (("EMAIL_FORMAT", "email", email_valid),
                               ("IFSC_FORMAT", "ifsc_code", ifsc_valid),
                               ("ACCOUNT_NUMBER_FORMAT", "bank_account_number", account_valid)):
        if _text(data.get(field)).strip() and not valid:
            rejected.add(code)
    if gstin:
        if not gst_format:
            rejected.add("GSTIN_FORMAT")
        else:
            if not state_valid:
                rejected.add("GSTIN_STATE_CODE")
            if not checksum_valid:
                rejected.add("GSTIN_CHECKSUM")
    return [make_check(code, "PASS" if passed else "REJECTED" if code in rejected else "PENDING", good if passed else bad)
            for code, passed, good, bad in specifications]


def detect_mime(content):
    if not isinstance(content, bytes):
        return None
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def inspect_document(document_type, uploaded_file):
    code = f"{document_type}_UPLOAD"
    def pending(message):
        return None, make_check(code, "PENDING", message)
    if document_type not in REQUIRED_DOCUMENT_TYPES:
        return pending("Unsupported upload category.")
    label = {"GST_CERTIFICATE": "GST registration certificate", "BANK_PROOF": "bank account proof"}[document_type]
    if uploaded_file is None:
        return pending(f"Required document missing: {label}.")
    try:
        content = uploaded_file.getvalue()
    except Exception:
        return pending("Uploaded document could not be read.")
    if not isinstance(content, bytes) or not content:
        return pending("Uploaded document is empty or unreadable.")
    if len(content) > MAX_DOCUMENT_SIZE:
        return pending("Uploaded document exceeds the 5 MB limit.")
    mime_type = detect_mime(content)
    if mime_type is None:
        return pending("Uploaded document is not a supported PDF, PNG, or JPEG.")
    try:
        if mime_type == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                return pending("Encrypted PDFs are unsupported. Upload an unencrypted copy.")
            if not 1 <= len(reader.pages) <= MAX_DOCUMENT_PAGES:
                return pending(f"PDF must contain 1–{MAX_DOCUMENT_PAGES} pages.")
        else:
            from PIL import Image
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        return pending("Image exceeds the configured 20 megapixel limit.")
                    image.verify()
    except ImportError:
        return pending("Document validation dependency is unavailable; technical review required.")
    except Exception:
        return pending(f"The {label} could not be read. Upload a clear, valid PDF or image and resubmit.")
    document = {"filename": _text(getattr(uploaded_file, "name", "")) or "document",
                "content": content, "mime_type": mime_type}
    return document, make_check(code, "PASS", "Document is readable and uses a supported file format; authenticity is unverified.")


def check_duplicate(existing_vendor):
    if existing_vendor is None:
        return make_check("DUPLICATE_GSTIN", "PASS", "No existing registration with this GSTIN was found.")
    existing_id, status = existing_vendor["submission_id"], existing_vendor["status"]
    reference = f"VND-{int(existing_id):06d}"
    if status == "APPROVED":
        return make_check("DUPLICATE_GSTIN", "REJECTED", f"An approved vendor already exists under {reference} with the same GSTIN.")
    if status == "REJECTED":
        return make_check("DUPLICATE_GSTIN", "PASS", f"Previous application {reference} was rejected; this new application requires all checks again.")
    if status in {"PENDING", "SUBMITTED", "PROCESSING"}:
        return make_check("DUPLICATE_GSTIN", "REJECTED", f"An active application already exists under {reference} with the same GSTIN. Continue or correct that application instead of creating another registration.")
    return make_check("DUPLICATE_GSTIN", "PENDING", f"GSTIN is associated with existing submission {reference}. Correct that application or request human review.")


def _document_correction_message(document_type, extracted):
    label = "GST certificate upload" if document_type == "GST_CERTIFICATE" else "Bank proof upload"
    subtype = _text(extracted.get("document_subtype")) if isinstance(extracted, Mapping) else ""
    finding = {
        "GSTIN_INFOGRAPHIC": "contains an educational GSTIN infographic, not registration evidence",
        "GSTIN_SCREENSHOT": "contains only a GSTIN screenshot, not a registration certificate",
        "UNREADABLE": "is blank or unreadable",
        "UNSUPPORTED": "does not provide the required supporting evidence",
    }.get(subtype, "was not identified as the required document type")
    action = (
        "Replace it in VENDENCE with a clear, complete GST registration certificate "
        "(Form GST REG-06) showing the registered legal name and GSTIN, then resubmit."
        if document_type == "GST_CERTIFICATE" else
        "Replace it in VENDENCE with a clear bank statement, account confirmation, or cancelled cheque "
        "showing the account holder, account number, bank name, and IFSC, then resubmit."
    )
    if document_type == "GST_CERTIFICATE" and subtype == "GSTIN_INFOGRAPHIC":
        return f"The uploaded GST certificate is invalid. {action}"
    return f"{label} {finding}. {action}"


def check_document_evidence(document_type, data, extracted):
    """Compare explicit evidence; legal names must never fall back to trade names."""
    if document_type not in DOCUMENT_COMPARISONS:
        return [make_check("DOCUMENT_IDENTITY", "ERROR", "Unsupported document category.")]
    if not isinstance(extracted, Mapping) or extracted.get("document_type") != document_type:
        return [make_check(f"{document_type}_IDENTITY", "PENDING", _document_correction_message(document_type, extracted))]
    # Legacy BANK_PROOF records remain viewable; newly extracted responses include subtype.
    subtype = extracted.get("document_subtype")
    acceptable_subtypes = {"GST_CERTIFICATE": {"GST_REGISTRATION_CERTIFICATE"},
                           "BANK_PROOF": {"BANK_STATEMENT", "BANK_ACCOUNT_CONFIRMATION", "CANCELLED_CHEQUE"}}
    if subtype is not None and subtype not in acceptable_subtypes[document_type]:
        return [make_check(f"{document_type}_IDENTITY", "PENDING", _document_correction_message(document_type, extracted))]
    results = [make_check(f"{document_type}_IDENTITY", "PASS", "AI identified the required document category; this is not an authenticity finding.")]
    for form_field, extracted_field, mode in DOCUMENT_COMPARISONS[document_type]:
        expected, actual = data.get(form_field), extracted.get(extracted_field)
        label = REQUIRED_FIELDS[form_field]
        outcome = "PENDING"
        if not _text(expected).strip() or not _text(actual).strip():
            message = f"Could not verify {label.lower()} against the document; required evidence is missing."
            matches = False
        else:
            matches = same_value(expected, actual, mode)
            message = (f"{label} matches the uploaded document." if matches else
                       f"{label} differs from the uploaded document. Correction or human review required.")
            if (not matches and document_type == "BANK_PROOF" and form_field == "bank_account_holder"
                    and subtype in acceptable_subtypes["BANK_PROOF"] and holder_names_clearly_differ(expected, actual)):
                outcome = "REJECTED"
                message = ("The account holder name does not match the uploaded bank document. "
                           "Correct the name or upload matching bank proof, then resubmit.")
        results.append(make_check(f"{document_type}_{form_field.upper()}_MATCH", "PASS" if matches else outcome, message))
    return results


def check_approval_policy(policy="strict", synthetic_declared=False):
    valid = policy in APPROVAL_POLICIES
    results = [make_check("APPROVAL_POLICY", "PASS" if valid else "ERROR",
                          "Strict independent verification policy applies." if policy == "strict" else
                          "Synthetic demonstration consistency policy applies; no independent legal or banking verification is claimed." if valid else
                          "Unknown approval policy; approval is disabled.")]
    if policy == "demo_consistency":
        results.append(make_check("SYNTHETIC_DATA_DECLARED", "PASS" if synthetic_declared is True else "PENDING",
                                  "Submission explicitly declared synthetic for demonstration use only." if synthetic_declared is True else
                                  "Demonstration approval requires an explicit synthetic-data declaration."))
    return results


def check_authenticity(document_type, verification=None, policy="strict"):
    """Only recorded authorized verification can establish VERIFIED.

    The caller must obtain the record from the current document/revision, never
    from Gemini or applicant-supplied text. A registry lookup alone confirms a
    taxpayer record, not the authenticity of the uploaded certificate.
    """
    code = f"{document_type}_AUTHENTICITY"
    if document_type not in REQUIRED_DOCUMENT_TYPES or policy not in APPROVAL_POLICIES:
        return make_check(code, "ERROR", "Unsupported authenticity verification configuration.")
    if verification is not None and not isinstance(verification, Mapping):
        # sqlite.Row supports keys but is not a Mapping.
        try:
            verification = dict(verification)
        except (TypeError, ValueError):
            return make_check(code, "ERROR", "Invalid authenticity verification record.")
    verification = verification or {}
    state = verification.get("state", "NOT_VERIFIED")
    if state not in AUTHENTICITY_STATES:
        return make_check(code, "ERROR", "Unknown authenticity verification state; human review required.")
    if state == "VERIFICATION_FAILED":
        return make_check(code, "PENDING", "Independent authenticity verification failed; human review required.")
    if state == "VERIFIED":
        # An arbitrary note or AI model is not an authorized verification method.
        methods = {"GST_CERTIFICATE": {"GST_PORTAL_AND_ORIGINAL", "TRUSTED_DIGITAL_SIGNATURE", "AUTHORIZED_REVIEW"},
                   "BANK_PROOF": {"BANK_CONFIRMATION", "AUTHORIZED_REVIEW"}}
        if verification.get("method") not in methods[document_type] or not all(
                _text(verification.get(field)).strip() for field in ("reviewer", "evidence_reference")):
            return make_check(code, "ERROR", "VERIFIED lacks an authorized method, reviewer, or evidence reference.")
        return make_check(code, "PASS", "VERIFIED through a recorded authorized verification process; scope and evidence are available in the audit history.")
    if policy == "demo_consistency":
        return make_check(code, "PASS", "NOT_VERIFIED. Explicit synthetic demonstration policy permits consistency approval only; no independent authenticity, taxpayer, or bank-account verification occurred.")
    return make_check(code, "PENDING", "NOT_VERIFIED. Strict approval requires recorded authorized verification of this document; AI classification and matching are insufficient.")


def required_check_codes(policy="strict"):
    codes = {f"REQUIRED_{field.upper()}" for field in REQUIRED_FIELDS}
    codes.update({"APPROVAL_POLICY", "EMAIL_FORMAT", "COUNTRY_SCOPE", "GSTIN_FORMAT", "GSTIN_STATE_CODE",
                  "GSTIN_CHECKSUM", "IFSC_FORMAT", "ACCOUNT_NUMBER_FORMAT", "SUBMITTED_BANK_HOLDER", "DUPLICATE_GSTIN"})
    for document_type in REQUIRED_DOCUMENT_TYPES:
        codes.update(f"{document_type}_{suffix}" for suffix in ("UPLOAD", "AI_EXTRACTION", "IDENTITY", "AUTHENTICITY"))
        codes.update(f"{document_type}_{field.upper()}_MATCH" for field, _, _ in DOCUMENT_COMPARISONS[document_type])
    if policy == "demo_consistency":
        codes.add("SYNTHETIC_DATA_DECLARED")
    return frozenset(codes)


def determine_decision(checks, required_codes=None, policy="strict"):
    """Approve only a complete, unique set of explicit PASS outcomes.

    Unknown, malformed, missing, duplicate, failed and error checks fail closed.
    Additional configured checks must pass too; explicit rejection wins.
    """
    if policy not in APPROVAL_POLICIES:
        return "PENDING", "Unknown approval policy; approval is disabled."
    try:
        required = required_check_codes(policy) if required_codes is None else frozenset(required_codes)
    except (TypeError, ValueError):
        return "PENDING", "Required verification check configuration is invalid; approval is disabled."
    if not required or any(not isinstance(code, str) or not code for code in required):
        return "PENDING", "Required verification checks are not configured; approval is disabled."
    if not isinstance(checks, (list, tuple)) or not checks:
        return "PENDING", "No verification checks were completed; approval is disabled."
    issues, seen, rejected, nonpassing = [], set(), False, False
    for check in checks:
        if not isinstance(check, Mapping):
            issues.append("A verification check is malformed.")
            continue
        code, outcome, message = check.get("code"), check.get("outcome"), check.get("message")
        if not isinstance(code, str) or not code or not isinstance(message, str) or not message.strip():
            issues.append("A verification check is incomplete or malformed.")
        else:
            if code in seen:
                issues.append(f"A verification check was repeated: {code.replace('_', ' ').title()}.")
            seen.add(code)
        if outcome == "REJECTED":
            rejected = True
        if outcome != "PASS":
            nonpassing = True
        if outcome != "PASS" and (not isinstance(message, str) or not message.strip()):
            issues.append("A check did not explicitly pass.")
    issues.extend(summarize_check_issues(checks))
    missing = required - seen
    if missing:
        issues.append("Required checks are incomplete: " + ", ".join(code.replace("_", " ").title() for code in sorted(missing)) + ".")
    if rejected:
        return "REJECTED", "\n".join(dict.fromkeys(issues))
    if issues or nonpassing:
        return "PENDING", "\n".join(dict.fromkeys(issues)) or "Verification is incomplete. Review the individual checks."
    if policy == "demo_consistency":
        return "APPROVED", "All configured synthetic demonstration consistency checks passed. Document authenticity remains NOT_VERIFIED unless separately recorded; no independent government or banking verification is claimed."
    return "APPROVED", "All configured strict approval checks passed, including recorded authorized document verification. Verification methods and scope are available in the audit history."
