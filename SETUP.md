# Run VENDENCE locally

## Fresh installation

Download or clone the repository and open a terminal in its folder. Install Python 3.14, then run:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -c requirements-lock.txt
cp .env.example .env
```

Open `.env` locally and enter your Gemini key after `GEMINI_API_KEY=`. Do not share or commit the key. If `.env` already exists, keep it and edit it rather than copying over it.

On Windows, use `py -3.14 -m venv .venv`, replace `.venv/bin/python` with `.venv\Scripts\python.exe`, and use `Copy-Item .env.example .env` in PowerShell.

The configured Gemini model must be available to your account. Change `GEMINI_MODEL` locally if needed. API availability and quotas are external requirements; the automated unit tests use mocks and do not require credentials.

## Start

1. Open Terminal.
2. Run:

```sh
.venv/bin/python tools/run_browser_test_app.py --synthetic-consistency-demo --port 8502
```

3. Open http://127.0.0.1:8502/.
4. Keep Terminal open. Press Control-C to stop the app. Restart after changing Python modules.

Use port **8502** for this rehearsal. Close older VENDENCE tabs on other ports; a separate instance can use a different approval policy. The launcher above explicitly selects the synthetic consistency policy. The code default and `.env.example` remain strict. Do not use the sample policy for real vendor verification.

The existing Gemini key in `.streamlit/secrets.toml` is supported. No email-service account or SMTP configuration is needed. For a fresh installation, create `.venv` with Python 3.14, install `requirements.txt` using `requirements-lock.txt` as constraints, and configure Gemini privately using `.env.example` or Streamlit secrets.

The launcher declares a synthetic-only workspace and uses the consistency policy for sample inputs. The vendor form submits directly; the policy and declaration remain recorded in the checks. For strict verification instead, omit `--synthetic-consistency-demo`; strict approval requires recorded independent evidence. Reviewer actions require a separate locally configured `VENDENCE_REVIEWER_PASSWORD`.

## Submit and receive the result

1. Open **New Onboarding** and complete company/bank information.
2. Search for the bank in **Bank Name**. If it is unlisted, type its full name and press Enter. Use **ICICI Bank** for Approved/Rejected samples and **Axis Bank** for Pending. Upload the PDFs from the corresponding `testing/` subfolder; all form values are in `DEMO.md`.
3. Select **Submit and verify**. All required fields and both documents must be present first; the form lists missing items without creating an application or starting AI processing. Actual execution stages appear once the complete form is accepted.
4. Read the **Application status** dialog: ID, status, reason and checks.
5. Keep the application ID. **View application** opens Verification Center.

## Correct and resubmit

1. Open **New Onboarding -> Continue an existing application**.
2. Enter the application ID shown after submission.
3. Correct fields or replace the requested documents. Leaving an upload empty keeps its saved document.
4. Select **Resubmit and verify**. The new result appears; the ID remains unchanged.

Earlier documents, decisions and revisions remain in history. Approved applications are not directly editable; Pending and Rejected applications can be corrected. IDs are navigation within this local workspace, not authentication for an external vendor portal.

## Repeat checks

```sh
.venv/bin/python -m unittest discover -q
.venv/bin/python tools/run_live_workflow.py --synthetic-consistency-demo
```

The integration command calls real Gemini using fictional documents and a new isolated store. To retry an isolated Pending run, append `--resume-run` with the directory printed by that run. Existing vendor records remain untouched.

Use a separate `VENDENCE_DATA_DIR` for rehearsal if you need a fresh store. Reusing an already approved or active GSTIN deliberately produces duplicate rejection; corrections exclude their own application ID. Public hosting is not part of this local setup.

## Fresh multi-scenario integration batch

Prepare the three-PDF-case manifest with `.venv/bin/python tools/create_browser_fixtures.py`. Then run `.venv/bin/python tools/run_e2e_batch.py --manifest tmp/qa_inputs/three_case_manifest.json --output tmp/qa_runs/new_rehearsal --real-gemini`. The default store is isolated and existing vendor records are retained. This batch checks Approved, Pending and Rejected using the shipped PDFs. Use a new output folder for a new batch. It never resets data. Broader exception cases remain covered by the automated tests.
