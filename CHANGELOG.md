# VENDENCE changelog

## 19 October 2026: PDF-only rehearsal library

Replaced the scattered image/demo input library with testing/1_Approved, testing/2_Pending and testing/3_Rejected, each containing two professional one-page PDFs. ICICI Bank and Axis Bank names use fictional data and visible sample labels. Approved has matching registration/statement evidence; Pending uploads a tax invoice as registration evidence; Rejected has a supplied-holder contradiction. All three complete workflows passed with real Gemini in an isolated store, all six pages passed rendering/text checks, and all 166 automated tests passed after cleanup. Updated helper paths, manifest generation, setup/demo instructions and source packaging. Archived old demo_inputs/demo_runs and the two superseded image/Word generators in backups/before_pdf_testing_cleanup_20261019T131801Z/. Existing database rows and uploaded application evidence are unchanged. ReportLab is optional PDF authoring tooling, not an app runtime dependency.

## 19 October 2026: reject clear bank-holder contradictions

validation.py now rejects a supplied holder name that clearly contradicts readable, recognized bank evidence. Missing/masked names, initials, shared names and possible spelling/abbreviation differences remain Pending; similarity never passes a comparison. Company-name differences alone and other bank-field mismatches retain their existing behavior. The decision summary avoids repeating the less specific company/holder warning when bank evidence establishes the rejection. Added validation, full-workflow and UI correction regressions; all 166 automated tests pass. Updated README.md, WORKFLOW.md, DEMO.md and new fixture expectations. Rechecked VND-000003 against its saved real-Gemini extraction: Rejected, same ID, previous Pending audit retained, no new API calls or applications. Applications 1–2 and all uploaded files are unchanged.

## 19 October 2026: concise approval result

Shortened the demonstration approval message in the result dialog, saved result, Verification Center and Vendor Registry through ui.py presentation formatting. Detailed policy checks, document authenticity status and original audit wording remain intact; decision rules and stored records are unchanged. Added an approval-display/audit-preservation regression in tests/test_app.py, including preservation of extra warnings. All 162 automated tests pass.

## 19 October 2026: consistent local happy-path configuration

Investigated the user's Pending happy path: every comparison passed, but the saved run used strict policy and lacked independent authenticity evidence. Found two local VENDENCE instances and strict configuration in the private local environment. Explicitly configured this fictional rehearsal workspace for demo consistency with its synthetic-only declaration, retained strict code defaults, stopped both instances and restarted one localhost instance on port 8502. The exact happy-path PDFs passed all 33 checks through real Gemini in isolated storage; authenticity remained Not Verified. All 161 automated tests pass. Backed up and cleared the one active application and related tables/uploads as requested. Updated SETUP.md and VERIFICATION.md; no decision rules were weakened or audit results rewritten. Manual tests now proceed one at a time, awaiting the user's result after each scenario.

## 19 October 2026: prevent repeat submissions

Reproduced the completed form's active Submit button creating extra applications. app.py now retains the saved result in the current browser session and replaces the form after a saved attempt, including Pending technical outcomes. ui.py clears that state only on an explicit new-application action. Incomplete forms and failures before saving remain retryable; same-ID correction is unchanged. Added three delayed-submit/navigation regressions and extended database-failure retry coverage in tests/test_app.py. Simplified the infographic replacement message in validation.py and its historical display in ui.py without rewriting audit data. Added a history-preservation regression and adjusted evidence/workflow tests. All 161 automated tests pass. Saved vendor data and theme are retained.

## 19 October 2026: interface wording

Simplified slogans, page titles, repeated form instructions and technical captions in ui.py and app.py. Unconfigured reviewer setup is hidden; configured reviewer access and explicitly simulated failures remain labeled. Kept decision reasons, document authenticity states and audit history. The pink/lavender/purple CSS, approval rules and saved records are unchanged. Added two UI regressions in tests/test_app.py; all 157 automated tests pass. Reviewed all four rendered pages without new submissions or Gemini calls.

## 19 October 2026: fresh end-to-end rehearsal

Backed up and verified the prior database/uploads, then cleared all eight tables and active uploads as authorized. Ran fresh randomized synthetic browser and real-Gemini cases; the active registry now has 15 applications: 7 Approved, 6 Pending, 2 Rejected. Verified corrections, duplicates, input formats, wrong/corrupt/oversized documents, strict fabricated evidence, actual previews, outage recovery, file hashes, audit redaction and restart persistence.

Fixed the corrupt-document replacement message in validation.py, restricted legacy extraction backfill in database.py to schema upgrades, and fixed stale filtered selection/empty-result wording in ui.py. Added seven regressions and strengthened separate-process restart coverage: 155 automated tests pass. Added tools/run_e2e_batch.py with isolated storage by default, redacted evidence and same-ID retry; extended fresh fixture generation with bank statements and unique identifiers. Current evidence is in VERIFICATION.md and demo_runs/e2e_20261019T074118Z/. CSV download confirmation was deferred by the user and remains unverified. No email, hosting, video, visual redesign or new vendor workflow added.

## 19 October 2026: required form inputs and concise reasons

Added completeness validation before saving or processing vendor submissions/corrections in app.py and validation.py. Missing fields and uploads are grouped; no new record, revision or AI request is made until complete. Corrections can retain saved documents. Decision explanations group missing information and suppress dependent check repetition while preserving all detailed checks and fail-closed outcomes. Fixed repeated Business Email / IFSC Code wording in ui.py. Updated form regressions to submit complete fixtures and added eight regressions for incomplete forms, document reuse, audit preservation, complete submission, label formatting and safe concise explanations. All 148 tests passed with temporary storage and mocked Gemini; compilation passed. Existing 15 applications retained.

## 19 October 2026: submit heading

Removed the Start verification heading from the vendor form; the submit and resubmit buttons remain in place. Python compilation passed.

## 19 October 2026: direct vendor submission

Removed the policy callout, synthetic-data checkbox and technical submission caption from new and correction forms in ui.py. The explicit synthetic-demo launcher now declares the synthetic-only workspace outside the form; app.py passes that configuration to the existing audited checks. Strict policy and undeclared demonstration runs retain their approval guards. Updated setup and authenticity documentation. All 140 automated tests passed, including direct submit/correction and strict/undeclared-policy guards. Compilation passed; all 14 existing applications retained.

## 19 October 2026: upload caption

Removed the testing-specific educational GSTIN diagram caption from the vendor upload form. Document classification and verification rules are unchanged.

## 19 October 2026: bank dropdown and verified cleanup

Changed ui.py to provide a searchable Bank Name dropdown with native unlisted-name entry, no implicit default, and saved-name preservation on corrections. The existing bank-name check uses the selected value. Updated validation.py only for bank-specific Ltd./Limited suffix normalization; different-bank mismatches remain Pending and company-name rules remain unchanged. Added six UI/workflow/normalization regressions; 138 tests passed. The browser fixture generator now expects invalid checksums to be Rejected; generated all 12 scenarios in temporary storage and verified their paths.

Checked dependencies before removing six unused hosting/report files from the active root and retaining recovery copies. Removed six unpacked export folders only after exact ZIP comparison, archived eight old ZIPs, and preserved one differing folder. Updated tools/package_source.py and current instructions, keeping source exports focused on local operation. Retained useful fixture/test tools, real run evidence, private configuration and all vendor data. All original rows in eight tables and all 28 upload hashes match backups/before_bank_dropdown_cleanup_20261018T214106Z/; all 14 applications preserved. Compilation passed. No email code, public deployment or new workflow added.

## 19 October 2026: invalid formats and active duplicates

Changed validation.py so supplied invalid email, IFSC and configured account-number formats reject. Missing values retain the current Pending policy. Duplicate GSTINs against another Pending, Submitted or Processing application now reject, referencing the existing ID; database.py enforces the same rule atomically. Approved duplicates still reject. Same-ID corrections and fresh processing after Rejected history remain allowed. Updated existing rule tests and added five workflow/database regressions; 132 tests passed. Updated current instructions and decision tables. Existing records and uploaded evidence remain unchanged.

## 19 October 2026: decision labels

Replaced the displayed Needs Review label with Pending in result views, dashboard counts, Registry filters and current instructions. Registry decision filters are Approved, Rejected and Pending. Internal processing stages and deterministic business rules remain unchanged. Updated the existing UI filter regression; all 16 UI tests passed.

## 19 October 2026: in-app results and simpler interface

At the user's request, removed email sending, SMTP configuration/loading, mail-related approval requirements, delivery panels and mail smoke/integration tests. Deleted notifications.py, tools/check_email.py and tests/test_notifications.py. Removed transport helpers from workflow.py/database.py; legacy data tables/rows remain untouched. Updated the standalone real-Gemini tool and optional deployment settings.

Added an immediate Application status dialog in ui.py, opened by app.py after processing. It shows ID/status/reason/checks and routes to the current application's correction form. The saved result and same-ID resubmission/history remain available. Removed Overview's Verification approach, the technical upload-category warning, and redundant boundary explanations; preserved document classification/authenticity safeguards and the existing visual design. Supplied GSTINs with invalid structure/state/checksum now reject; missing GSTIN remains Pending. Rejected submissions can be corrected under the same ID.

Changed app.py, ui.py, workflow.py, database.py, validation.py, config.py, .env.example/local SMTP entries, tools/run_live_workflow.py, tools/export_browser_test_report.py, render.yaml, regression tests and current documentation. Baseline 147 passed; current **127 passed, 0 failed** after removal of obsolete transport tests and addition of feedback/GSTIN regressions. Real Gemini run returned Approved with 33 Passed checks and Not Verified authenticity, with no mail service. Compilation passed. All original rows in eight active tables and uploaded file hashes match the checkpoint; all 14 existing applications retained.

Browser inspection was blocked by the access policy for the existing error-page tab; AppTest verified dialog content and actual submission-to-correction navigation instead. Updated localhost server starts. No public hosting, video recording, external sending or data deletion. Prior reports are marked historical and the sanitized source package is refreshed.

## 17 October 2026: independent approval and assignment audit

Reread the full guide and traced the core application, tests, persistence and provider assumptions. Baseline: 139 tests passed. Five new targeted checks failed: caller-only passes, saved failures hidden by caller results, passes reused from an earlier run, failed authenticity bypass at demo finalization, and receipt absent from the required inventory.

Changed `database.py` and `validation.py`: approval now requires matching durable checks created in the current run, independently rechecks authenticity under both policies, rejects paths outside upload storage, and uses policy-generated approval explanations. Added one additive run-boundary column (schema version 3) and made receipt communication a required configured check. Expanded `tests/test_database.py`, preserving the attack probes and updating valid approval fixtures to explicitly save their results. Three further regressions cover hidden extra errors, mismatched explanations and invented certification wording.

Executed: **147 tests passed, 0 failed**; fresh real Gemini + loopback SMTP Approved with 34 Passed checks/two captured messages/both documents Not Verified; pip check passed. Cold-started localhost and checked dashboard and existing-ID correction navigation. All original rows in eight active data tables and all 26 upload hashes match `backups/before_independent_audit_20261016T171948Z/`; current 13 applications and their histories remain intact. No UI styling change, vendor-data deletion, Mailtrap send, public hosting or publication. Added `INDEPENDENT_AUDIT.md` with primary-source research and updated alignment/workflow/verification notes. Video and process-access arrangements remain candidate-owned/deferred.

## 16 October 2026

### Baseline and checkpoint

Inspected the existing working modules, SQLite schema, dependencies, workflow, UI, and seven-page candidate guide. No existing automated tests or Git repository were present. The baseline Streamlit app rendered all four sections. Regression probes reproduced approval from empty, Fail, Error, and unknown outcomes. Saved code, a consistent SQLite backup, and document originals in `backups/checkpoint_20261016T065008Z`; no API secrets were copied into the checkpoint.

### Approval safety and validation

Changed `validation.py`, `ai_service.py`, and their tests. Added fail-closed required-check completeness, GSTIN checksum/current-state rules, consistent normalization, conservative name matching, structured document subtypes, bounded document parsing, and strict versus declared synthetic policies. Gemini never controls final approval or authenticity. SDK retries are explicitly bounded for a predictable live workflow. Format checks clearly distinguish syntax from independent existence verification.

### Persistence and corrections

Changed `database.py`, added `workflow.py`, and integrated them through `app.py`. Added idempotent schema migrations, revision snapshots, preview paths, immutable document/extraction history, current checks, reviewer evidence, communication logs, and atomic duplicate/finalization checks. Corrections retain the ID and earlier evidence. Invalid replacements cannot silently reuse old documents. Recovery invalidates stale workers. Compared all original columns against the checkpoint: all 5 submissions, 2 documents, and 49 events remained unchanged; SQLite integrity was OK.

### Interface and communication

Extended `ui.py` while preserving the original CSS exactly. Added correction forms, current-revision checks, separate authenticity details/reviewer controls, document history, email outcomes, and reviewer/access gates. Installed the official Streamlit PDF component for inline previews. Added `notifications.py` with TLS SMTP and truthful Not Configured/Accepted/Failed states. Remote SMTP remains dependent on user-configured credentials; no real inbox delivery is asserted.

### Demonstration and deployment preparation

Added synthetic form/document fixtures, a Word-format imitation exported to PDF, setup/verification tools, `AUTHENTICITY.md`, `SETUP.md`, `DEPLOYMENT.md`, and `DEMO.md`. Added pinned runtime requirements, a Docker image definition, data/secret exclusions, and a paid Render persistent-disk template. No public hosting resources were provisioned. Docker is unavailable locally, so container execution and hosted persistence remain unverified.

### Executed verification

121 automated tests passed using `.venv/bin/python -m unittest discover -q`, including all seven required workflow scenarios, real loopback SMTP acceptance/refusal, migration/duplicate/concurrency regressions, correction/audit history, technical failures, AppTest navigation/access/reviewer separation, preview paths, and storage across a separate Python process restart. Python compilation and pip dependency consistency checks passed. The original pink/lavender/purple CSS matched the checkpoint exactly.

Controlled real Gemini calls initially returned provider 503/504 errors, demonstrating safe extraction failure. Model discovery succeeded. Later, all six real classification checks passed: GST certificate and field comparisons, bank confirmation PDF and field comparisons, infographic, GSTIN-only screenshot, unreadable image, and fabricated Word-to-PDF certificate. The fabricated document was recognized as certificate-shaped but its strict authenticity check remained Pending. Every document's independent authenticity remained Not Verified. Reports are saved privately under `demo_runs/`; no mocked result is reported as live AI.

An isolated complete onboarding run then used real Gemini for both PDFs and a real loopback SMTP test inbox. It completed 34 checks and returned Approved under the explicitly selected synthetic consistency policy. Two notifications were accepted and captured locally; both document authenticity states remained Not Verified. The existing application database was not used. Browser startup and the actual onboarding page were also checked, with a private screenshot saved under `tmp/browser_qa/`.

### Remaining release gates

After the user configured SMTP locally, the setup smoke test returned Accepted. A complete isolated onboarding then used real Gemini and the configured email provider; all 34 checks passed, receipt and decision notifications were both accepted, and the explicit synthetic consistency decision was Approved. Both document authenticity states remained Not Verified. No credentials were printed or packaged. The provider report is `demo_runs/live_workflow_20261016T095859Z/report.json`; the user confirmed the setup email appeared in Mailtrap.

Current remaining work: rehearse the local browser happy path and 2–4 selected edge cases, then record the five-minute video. Submission access for the guide’s requested process link needs separate clarification. Public hosting is outside the current scope.


### Scope clarification after full guide reread

The user explicitly wants a local case-study project and does not want public hosting. Reread all seven pages of the candidate guide. Pages 1–2 request a live runnable process link and a five-minute video; page 4 specifies PS-2 decisions, reasoning, follow-up, and 2–4 meaningful edge cases; pages 6–7 emphasize actual execution and prepared live demonstrations. The guide does not explicitly prescribe public cloud hosting. Hosting was carried forward from the earlier project brief; it is now removed from the current required next steps. Updated setup, workflow, demo, and verification notes accordingly. Working application code and vendor data were unchanged by this documentation correction.

### Fresh actual-browser testing and fixes

At the user's explicit request, backed up the old five vendors and documents to `backups/before_browser_reset_20261016T101931Z/`, reset the active test store, and generated randomized, watermarked fictional GST/bank/invoice/negative image inputs. No confidential documents or credentials were used as test inputs.

Executed 13 fresh applications and 20 processing revisions through the actual Streamlit browser: all seven core scenarios and seven additional negative cases. Final registry has 2 Approved, 10 Pending, 1 Rejected. Both approvals are explicitly synthetic consistency approvals with 34 Passed checks and Not Verified authenticity. Correcting the infographic submission preserved its ID, three revisions, and old documents. Real timeout/503 failures were retained and retried; they were not counted as successful classifications.

Changed `ai_service.py` timeout to 60 seconds, `workflow.py` decision-notification selection, `notifications.py` safe rate/quota errors, sandbox pacing and application-reference redaction, and the missing-document label in `validation.py`. Added corresponding regressions: 125 tests pass. `app.py` labels the QA process and local scope; no styling redesign was made.

Added browser fixture/launcher/evidence tools and `BROWSER_TEST_REPORT.md`; updated verification, assignment alignment, local setup, and README. SQLite integrity is OK, foreign keys are intact, and dependencies are consistent. The batch recorded 40 SMTP acceptances and one earlier failed redundant send. After final refresh, the user confirmed both Pending and rejected emails in Mailtrap with clear explanations. Added a whitelisted local source-packaging tool for GitHub preparation; no repository was published. Video recording remains the candidate's deferred task.

### Specific document correction instructions

The user's captured emails showed that document-request explanations were too generic. Updated `validation.py` to identify the affected GST/bank upload and request suitable replacement evidence; updated `workflow.py` to explain deferred comparisons and distinguish technical retry from document replacement. Added validation and real loopback SMTP workflow regressions in `tests/test_validation.py` and `tests/test_workflow.py`; all 127 tests pass. Sent emails and active vendor records were not modified, and no additional Mailtrap quota was used. Refreshed verification notes and the sanitized source package.

### Complete guide re-audit and correction entry

Reread all seven pages as text and rendered images; rewrote ASSIGNMENT_ALIGNMENT.md to account for every section, separate software requirements from candidate-owned actions, and state policy/access limits. Saved source/data/document checkpoint `backups/before_guide_reaudit_20261016T162335Z/` before editing.

Five focused tests reproduced seven failing assertions/subcases: opening the wrong selected application, retaining approval after a reviewer withdrawal/failure, accepting unnamed review actions, leaking an account number through AI explanatory fields, and omitting a Pending email after an invalid AI response. Fixed these in `ui.py`, `app.py`, `database.py`, and `workflow.py`. Added local Continue an existing application navigation and Start another application clearing, preserving the existing CSS and four sections. `notifications.py` now explains the local resume steps and duplicate next action. Review withdrawal changes status/checks atomically, retains prior decisions and triggers an audited Pending message; failed transport cannot restore approval.

139 automated tests pass, including new UI/persistence/workflow regressions and real loopback SMTP. An initial redirected run was sandbox-blocked on seven local sockets; the permitted rerun passed. A fresh real Gemini integration returned Pending after bank HTTP 503, then Approved with 34 checks on explicit retry; loopback captured both messages and authenticity remained Not Verified. Extended the isolated integration tool with a guarded Pending-run retry that preserves the first report.

Browser checked invalid and valid resume IDs with correction expanded. Restarted the test server after observing a stale module; fresh startup loaded updated code. Active data remained exactly unchanged across 13 submissions, 39 document records, 20 revisions, 823 events and 41 email attempts. Integrity/foreign keys, dependencies and compilation passed. Updated workflow/setup/authenticity/demo/verification notes and source packaging. Candidate video, coordinator communication and submission access remain deferred/unverified; no public hosting or external publication was created.

Browser visual review also found Streamlit's `primaryFormSubmit` kind bypassing the existing purple button selector. Extended that selector and its hover rule in `ui.py`; palette, layout and the four sections remain intact. Verified the button color in the browser. This is a styling compatibility fix, not a redesign.
