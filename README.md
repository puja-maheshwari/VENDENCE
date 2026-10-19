# VENDENCE

Vendor onboarding for Zamp's PS-2 case study. A vendor submits company details and supporting documents; Gemini extracts the evidence and deterministic checks produce Approved, Pending, or Rejected.

## Install and run

Requires Python 3.14 and your own Gemini API key. Start from a downloaded copy of this repository, then run these commands in its folder (macOS/Linux):

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -c requirements-lock.txt
cp .env.example .env
```

Add your key to `GEMINI_API_KEY` in the local `.env` file. Never commit this file. Existing `.streamlit/secrets.toml` configuration is also supported. For Windows and further setup details, see [SETUP.md](SETUP.md).

Run the fictional sample workflow:

```sh
.venv/bin/python tools/run_browser_test_app.py --synthetic-consistency-demo --port 8502
```

Open http://127.0.0.1:8502/. Keep Terminal open; Control-C stops the app. Restart after Python module changes.

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`. Only Gemini credentials are required for document extraction. Model availability and API quotas depend on your Gemini account; `GEMINI_MODEL` can be configured locally.

## Vendor feedback and corrections

Submitting opens an **Application status** dialog showing the application ID, status, decision reason and checks. Select **View application** to open its details and correction form. The saved result remains in Verification Center and Vendor Registry after the dialog is dismissed.

To return later, open **New Onboarding -> Continue an existing application** and enter the ID shown after submission. Correct fields or replace documents, then select **Resubmit and verify**. The ID stays the same; previous revisions and evidence remain in history. Business Email remains a contact field; the app does not send email or need a mail account.

The existing pink/lavender/purple interface retains four sections: Overview, New Onboarding, Verification Center and Vendor Registry. Wrong documents are explained through the decision and checks rather than a separate technical classification warning.

Bank Name is a searchable dropdown of common choices. If a bank is not listed, type its full name and press Enter. The current PDF samples use ICICI Bank and Axis Bank. Synthetic demonstration mode also retains Example Demonstration Bank for older saved test records. The selected name is compared with the bank evidence; different banks block approval. Case, punctuation and Ltd./Limited suffix wording are normalized only for bank-name comparison. The list is a data-entry aid, not an exhaustive bank registry or account verification service.

## Decision rules

| Status | When |
| --- | --- |
| Approved | Every required check passes under the selected policy |
| Rejected | A supplied GSTIN, email, IFSC or account number fails configured format checks; another active/approved application already has that GSTIN; or the supplied holder name clearly contradicts recognized bank evidence |
| Pending | Missing information/documents, wrong or unreadable evidence, ambiguous holder names or other company/bank mismatches, incomplete strict verification, or a technical failure |

Rejected applications can be corrected and resubmitted under the same ID. The original decision remains audited. Country scope is Indian GST-registered vendors; account-format rules are documented in `WORKFLOW.md`.

Strict approval requires recorded authorized independent verification. The demonstration launcher explicitly permits fictional consistency approval while authenticity remains Not Verified; the operator declares synthetic-only inputs through the launcher, without an extra vendor checkbox. AI extraction does not certify government issuance or bank ownership.

## Verification

```sh
.venv/bin/python -m unittest discover -q
.venv/bin/python tools/check_gemini.py
.venv/bin/python tools/run_live_workflow.py --synthetic-consistency-demo
```

Unit tests isolate storage and mock Gemini. The last two commands contact real Gemini with synthetic fixtures. The workflow tool uses a separate store under `tmp/qa_runs/`. Current results and limits are in `VERIFICATION.md`; guide coverage is in `ASSIGNMENT_ALIGNMENT.md`.

## Architecture and data

`app.py` integrates navigation; `ui.py` owns presentation; `workflow.py` orchestrates processing; `validation.py` owns decisions; `ai_service.py` extracts documents; `database.py` owns persistence/revisions/audit; `config.py` loads configuration.

Local data is in `database/vendence.db` and `uploads/`. Preserve both together. Existing historical audit rows are retained, including events from earlier versions. An application ID provides local navigation, not remote vendor authentication.

The `testing/` folder contains six fictional PDF samples across Approved, Pending and Rejected. [DEMO.md](DEMO.md) contains the matching form values. Optional PDF regeneration uses `tools/create_testing_pdfs.py` with ReportLab; no additional dependency is needed to run the app with the shipped PDFs.

This repository contains no API credentials, vendor database, uploaded application files or private recovery backups. A fresh installation creates its own local database and uploads directory. Historical verification notes may reference private run reports that are intentionally excluded. `tools/package_source.py` creates a whitelisted local source ZIP.

This is a locally runnable application, not a hosted service. Sharing its source link does not provide a live browser session; reviewers need to install it with their own credentials or watch an arranged live demonstration.
