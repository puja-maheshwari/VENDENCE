# VENDENCE workflow

## Architecture

| File | Responsibility |
| --- | --- |
| app.py | Navigation, access gates, workflow integration and live stages |
| ui.py | Existing styling, forms, result dialog, checks, previews and history |
| workflow.py | Create, verify, correct and reprocess applications |
| validation.py | Formats, comparisons, authenticity policy and deterministic decisions |
| ai_service.py | Gemini content classification and structured extraction |
| database.py | Additive migrations, immutable uploads, revisions and guarded finalization |
| config.py | Private local settings and environment precedence |

## Processing

Before creating or correcting an application, the form checks completeness. Missing required fields or documents produce one grouped message per category; verification does not start and no application/revision is saved. Corrections may retain existing saved documents. The backend retains its own complete checks for direct calls and previously saved incomplete records. Decision summaries group missing information and omit blocked follow-on messages; all individual results remain persisted and visible.

1. Save the application and its ID. Corrections retain the ID and add a revision.
2. Acquire the current processing revision and record the approval policy/synthetic declaration.
3. Check legal name, business email, country, GSTIN, bank name, holder, account number and IFSC. Business Email is contact information, not a delivery requirement.
4. Check email syntax, India scope, GSTIN structure/state/checksum, IFSC and configured 9-18-digit account syntax, and submitted legal-name/holder consistency. Format checks do not establish existence.
5. Normalize GSTIN case and whitespace consistently. Duplicates of Approved, Pending, Submitted or Processing applications are Rejected; rejected history allows another attempt. Corrections exclude their own ID.
6. Validate actual document bytes, size, PDF encryption/page limits and image integrity. Save supported uploads immutably. An invalid replacement cannot fall back to its older version.
7. Gemini classifies actual content independently of upload labels and extracts structured evidence. Unchanged successful extraction can be reused with an audit event.
8. Compare GST legal name and GSTIN; compare account holder, number, IFSC and the selected/entered bank name. Preserve leading zeroes and keep trade/legal names separate. The bank dropdown allows unlisted names; bank-only comparison tolerates the terminal Ltd./Limited wording, while company legal-name rules remain unchanged. A clear account-holder contradiction against a recognized bank document is Rejected. Missing/masked names, initials, shared name tokens and possible spelling/abbreviation differences remain Pending; similarity never makes a comparison pass. A company-name difference alone remains Pending. Other bank-field mismatches retain their existing Pending behavior.
9. Evaluate authenticity separately. Strict approval requires authorized independent review bound to the current document/revision/hash. Explicit synthetic consistency approval leaves authenticity Not Verified; a failed verification blocks it.
10. Persist any unexecuted requirement as incomplete. Compute the deterministic decision and commit only if the processing revision is current. Approval requires matching durable checks from this run, current files/authenticity evidence and an atomic duplicate recheck.
11. Return the recorded status, reason and checks. The UI immediately opens **Application status** and replaces the submitted form with the persistent result. Repeated or delayed submit events and returning to New Onboarding retain that application; only **Start another application** (or the Overview new-application button) resets the form. An incomplete form or a failure before an ID is saved remains retryable. Verification Center and Registry retain access to the outcome.
12. Pending or Rejected applications can be corrected and resubmitted with their original ID. Prior inputs, documents and outcomes stay audited.

## Decision policy

| Status | Conditions |
| --- | --- |
| Approved | Every configured requirement explicitly passes |
| Rejected | Nonempty GSTIN with invalid structure/state/checksum; supplied email, IFSC or account number with invalid configured format; duplicate of another active or approved application; clear account-holder contradiction against recognized bank evidence |
| Pending | Missing information or evidence; wrong/unreadable/unsupported document; ambiguous holder comparison, company-name difference alone, or other document mismatch; incomplete or failed authenticity review; technical exception |

A blank GSTIN is missing information, so remains Pending. Case/whitespace formatting alone does not make a GSTIN invalid. A syntactically valid identifier does not prove registration. Unknown/missing/failed/error checks cannot approve. Explicit rejection takes precedence over incomplete checks; the reasons remain visible. Correcting a Rejected application is permitted and audited.

## Communication and interface

Vendor communication happens in the local application: result dialog, saved explanation, checks and correction route. No email transport, credentials, delivery attempts or delivery-related approval checks are executed. Historical records from earlier versions remain in the database and complete audit history. Obsolete mail checks/events do not appear in current checks or the concise activity table.

Overview shows counts, recent applications and activity. Verification Center shows the status/reason, originals, extracted fields, meaningful checks and history. The redundant approach/boundary callouts and technical upload-category warning have been removed. Category validation still runs and explains which replacement evidence is needed.

## Recovery and boundaries

Interrupted processing stays safe. Authorized recovery advances the revision and invalidates stale workers. Database failures are reported honestly if persistence is unavailable. Reviewer withdrawal changes Approved to Pending atomically and refreshes the recorded outcome. No continuous evidence monitor is configured.

Scope is Indian GST-registered vendors. No automatic registry lookup, CAPTCHA bypass, bank ownership API, cryptographic signature validator or remote vendor identity system is implemented. See `AUTHENTICITY.md` for verification scope and `SETUP.md` for operation. Public hosting remains outside the local case-study scope.

## Current test evidence

The fresh end-to-end batch and fixes are recorded in VERIFICATION.md. Legacy extraction history is backfilled only while upgrading an older schema; ordinary startup does not create extraction rows for copied/reused evidence. Registry filters explicitly synchronize the selected application ID with the browser.
