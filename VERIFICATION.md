# VENDENCE verification — 19 October 2026

## PDF-only recording rehearsal library

The current sample input library is testing/: exactly three subfolders and six PDFs, with no images, forms or metadata inside them. All pages were rendered and visually checked; bank ledgers and invoice totals reconcile. All 166 automated tests passed after cleanup. Samples are clearly labeled fictional demonstration copies and do not contain seals, signatures, authentication QR codes or assertions of actual bank/government issuance.

Using real Gemini and isolated storage, the three shipped PDF pairs produced Approved, Pending and Rejected exactly as expected, with no technical error checks. Pending is caused by the invoice being the wrong GST document type; Rejected is caused by the supplied-holder contradiction. All document authenticity states remain Not Verified. New evidence is in tmp/qa_runs/pdf_rehearsal_20261019/backend_batch.json; fixture definitions are in tools/testing_cases.py. Existing vendor records and uploaded originals were preserved.

Old generated inputs and private run stores have been archived under backups/before_pdf_testing_cleanup_20261019T131801Z/retired_test_material/. Historical demo_inputs/ and demo_runs/ paths below refer to those archived materials. The two obsolete image/Word generators are also retained in that source checkpoint. Current run/check/package helpers use the six PDFs and keep generated manifests/reports under tmp/.

## Updated holder-mismatch policy

All 166 automated tests pass after changing clear holder contradictions against recognized bank evidence to Rejected. Tests cover the rejection message, incomplete/masked or ambiguous names remaining Pending, company-name differences alone, unchanged name normalization and rejected-to-approved correction under the same ID with audit preservation. Comparison similarity only routes uncertainty to Pending; it cannot produce a passing match.

VND-000003 was reprocessed with the saved, validated real-Gemini extraction. It is now Rejected with the concise correction message; no new API calls or applications were made. Its original Pending decision remains in audit history, and the policy recheck was recorded explicitly. Both approved applications and every uploaded file are unchanged. SQLite integrity and foreign keys passed. Source/database checkpoint, regression failure before the fix, passing test log and recheck report are in `backups/before_holder_rejection_20261019T130110Z/`. Earlier batch results below describe the policy at the time of those runs.

## Concise approval display

All 162 automated tests pass after shortening the approved-result wording in ui.py. The regression executes a complete mocked workflow, checks the concise result and visible Not Verified authenticity, and confirms the original policy reason remains in database/audit records. Additional warnings are not removed. The existing visual theme and decision rules are unchanged. This presentation change made no external AI calls or new active-store applications. Checkpoint and test log: `backups/before_concise_approval_20261019T125223Z/`.

## Local configuration diagnosis and fresh manual rehearsal

The user's new happy-path application was Pending solely because its saved approval policy was strict: GST and bank authenticity were Not Verified, while the other checks passed. Two VENDENCE instances were running on different ports. Configured this local fictional workspace explicitly for demo consistency and synthetic-only data, stopped the extra instance and restarted one app on localhost port 8502. Strict code defaults and the template remain intact.

Re-ran the exact `demo_inputs/1_happy/` PDFs with real Gemini in isolated storage: Approved, 33 checks, all passed, no technical error, both authenticity states Not Verified. Report: `demo_runs/live_workflow_20261019T124128Z/report.json`. All 161 automated tests passed with the local configuration present. Backed up the user's one Pending application and uploads, then cleared all eight active tables/uploads and reset application sequences, as requested. Database integrity is OK. Checkpoint and reset evidence: `backups/before_happy_path_config_fix_20261019T124109Z/`.

The active dashboard is empty for the user's fresh tests. Historical counts below describe earlier verification batches, not current active records. Manual guidance now covers only one scenario at a time; later recording and another reset await the user's request.

The current local application completed fresh UI, real-Gemini, backend, persistence and failure tests. The core rehearsal passed 155 automated tests. Subsequent interface wording and repeat-submission fixes added six UI regressions: **161 automated tests passed, 0 failed**. Source exports exclude runtime data and credentials; clean-package execution evidence is stored separately with each run.

## Repeat-submission regression and document message

Reproduced the active submit control remaining after a completed submission. The saved result now replaces that form in the current browser session; delayed submit events and returning to New Onboarding do not create another ID. An explicit new-application action opens a blank form. Tests cover Approved, Pending and Rejected outcomes, unchanged record/document/event counts, incomplete inputs, database-failure retry and same-ID correction.

An actual browser submission in separate temporary storage called real Gemini with the infographic and bank confirmation PDFs. It returned Pending with the shorter GST replacement message. Closing the dialog and navigating away/back retained the result without a submit control; Start another application opened a blank form, with exactly one saved application. No main-store records were added by this test. Evidence and the pre-change source are in `backups/before_repeat_submit_20261019T115300Z/`. Historical decision data remains intact; both newly processed results and historical display use the simplified wording.

## Interface wording review

Reviewed all four rendered sections after simplifying headings, slogans, repeated instructions and internal setup captions. Existing CSS and decision rules are unchanged; useful document guidance, reasons, authenticity states, reviewer controls when configured and audit history remain available. No new Gemini calls or submissions were needed for this presentation change. Copy-review evidence and the source checkpoint are in `backups/before_copy_polish_20261019T111741Z/`.

## Fresh test data

At the user's request, all eight existing data tables were cleared before testing. The previous 15 applications and 28 uploaded files are recoverable from `backups/before_fresh_e2e_20261019T074118Z/`; its database and upload hashes were checked before reset. Credentials and configuration were retained.

The active registry now contains **15 fresh synthetic applications: 7 Approved, 6 Pending, 2 Rejected**. It retains 54 document records across corrections and 31 distinct original files. No email is sent. No independent government or bank authentication is claimed.

## Executed scenario results

| Scenario | Observed result | Evidence / application |
| --- | --- | --- |
| GSTIN-only incomplete form | Blocked before save or AI; grouped missing fields and uploads | Actual browser; no application created |
| Complete fields without documents | Blocked before save or AI | Actual browser; no application created |
| Complete GST image + bank PDF | Approved under declared synthetic consistency policy | VND-000001; real Gemini |
| Approved GSTIN repeated with case/spacing changes | Rejected; original ID named | VND-000009 → VND-000001 |
| GSTIN infographic as registration evidence | Pending; replacement requested | VND-000011 revision 1; real Gemini |
| Replace incorrect document and resubmit | Approved with the same ID; original document/decision retained | VND-000011 revision 2; bank extraction reused |
| Submitted bank holder differs | Pending | VND-000012 revision 1; real Gemini |
| Duplicate of Pending GSTIN | Rejected; existing application named | VND-000013 → VND-000012 |
| Selected bank differs from proof | Pending | VND-000012 revision 2 |
| Valid-format account number differs from proof | Pending | VND-000012 revision 3 |
| Valid-format IFSC differs from proof | Pending | VND-000012 revision 4 |
| Typed unlisted bank name | Saved and compared; mismatching evidence stays Pending | VND-000012 revision 5 |
| Trade name used instead of legal name | Pending; no automatic legal-name substitution | VND-000012 revision 6 |
| Correct details with Pvt./Ltd. spelling variation | Approved; seven-revision audit retained | VND-000012 revision 7 |
| Invalid GSTIN checksum, email, IFSC and account length | Each Rejected, tested separately | VND-000014 revisions 1–4 |
| Correct rejected formats using saved evidence | Approved under same ID | VND-000014 revision 5 |
| Invoice uploaded as GST evidence | Pending; wrong document category | VND-000002; real Gemini |
| Invoice uploaded as bank proof | Pending; wrong document category | VND-000003; real Gemini |
| GSTIN-only screenshot | Pending | VND-000004; real Gemini |
| Blank page / unrelated image | Pending | VND-000005 / VND-000006; real Gemini |
| Fabricated Word-to-PDF certificate under strict policy | Pending despite matching fields; authenticity Not Verified | VND-000008; real Gemini |
| Synthetic bank statement PDF | Approved consistency result; classified Bank Statement | VND-000010; real Gemini |
| Controlled Gemini outage | Pending with extraction errors recorded | VND-000007; explicitly injected failure |
| Restore actual Gemini after outage | Approved under original ID; failed attempt retained | VND-000007; real Gemini recovery |
| Unsupported text / PNG larger than 5 MB | Blocked by actual upload control | Actual browser |
| Corrupt PDF | Pending; document-specific replacement instruction | VND-000015 revisions 1–2 |
| Replace corrupt PDF with readable GST evidence | Approved under same ID | VND-000015 revision 3; real Gemini |
| Database-write failure / malformed AI response | No false success or approval; errors handled | Isolated Streamlit regression tests |
| Registry ID/status/combined filters | Correct record counts and selected ID; clear empty result | Actual browser + regression |
| GST image and bank PDF previews | Original uploaded evidence rendered | Actual browser, VND-000001 |
| Cold restart | All eight table contents and all upload hashes preserved after fix | Full fingerprints + separate-process regression |

The live backend batch has nine successful scenario steps, including the explicitly simulated outage and subsequent real recovery. Twenty-eight recorded browser observations passed. CSV file saving remains a deferred manual check: the control was clicked, but the test browser exposed no download event; the user chose to check later. It is not reported as passed.

## Fixes found during this batch

- Corrupt-document feedback now names the affected upload and asks for a clear replacement.
- Startup only backfills old extraction history during the legacy-schema upgrade. It no longer creates new history rows for reused documents on every restart. Earlier attempts were retained; no application or file was lost.
- Filtering the registry now sends the replacement application ID to the existing browser widget. Previously its label could show the old ID while the details showed the filtered record.
- A filter with no matches now says so, rather than implying that no vendors exist.

The original visual design, four main sections, deterministic decisions and in-app communication remain in place. No public hosting, email transport or new vendor workflow was added.

## Integrity and scope

SQLite integrity is OK, foreign-key violations are zero, and every recorded document path/hash matches its file. Full bank-account values are absent from audit-event details, check messages and decision reasons. No authenticity attestations or email attempts were created. Unknown, missing, failed and error checks remain unable to approve.

The real-Gemini tests used fictional inputs. A synthetic consistency approval confirms configured matching checks; it does not authenticate legal or banking records. Strict fabricated-document testing correctly stayed Pending.

Local-only detailed evidence is in `demo_runs/e2e_20261019T074118Z/`: browser screenshots/observations, backend reports, database checks, restart fingerprints and test logs. A network-blocked first integration attempt and the initial failed restart comparison are preserved along with their successful retries. These private run stores and recovery backups are excluded from source exports.

## Repeat

```sh
.venv/bin/python -m unittest discover -q
.venv/bin/python tools/create_browser_fixtures.py
.venv/bin/python tools/run_e2e_batch.py --manifest <printed-fixture-folder>/manifest.json --output demo_runs/new_rehearsal --real-gemini
```

The batch runner defaults to a new isolated store. It never clears existing records. `--active-store` explicitly populates the local dashboard; use fresh inputs after an authorized reset to avoid expected duplicate rejections. `--resume` retries failed Pending runs under their original IDs and retains earlier attempts. Real Gemini availability/quota is external; automated tests use mocks and temporary storage.

Candidate recording and submission logistics remain candidate-owned. The core local demonstration is verified; manual CSV-download confirmation is still outstanding.
