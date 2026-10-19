# VENDENCE rehearsal inputs

The recording script remains deferred until the candidate confirms the three scenarios. The guide asks for a video of at most five minutes with a live happy path and at least one edge case. The intended recording shows Approved, Pending and Rejected, plus a brief view of saved reasons/history.

## PDF folder

Use only `testing/`. It contains three subfolders and six one-page PDFs. Every page is visibly labeled Sample - demonstration only. Bank names are ICICI Bank and Axis Bank; company identifiers, branch/account fields and transactions are fictional and are not independently verified.

| Folder | GST upload | Bank upload | Expected |
| --- | --- | --- | --- |
| 1_Approved | GST_Registration_Certificate.pdf | ICICI_Bank_Statement.pdf | Approved under the declared consistency policy |
| 2_Pending | Tax_Invoice.pdf | Axis_Bank_Statement.pdf | Pending; invoice is not GST registration evidence |
| 3_Rejected | GST_Registration_Certificate.pdf | ICICI_Bank_Statement.pdf | Rejected; supplied account holder contradicts the bank evidence |

## Form details

Common: Legal Company Name and Account Holder Name are Blue Orchid Supplies Private Limited; Business Email vendor@example.test; Country India; Account Number 000123456789 (retain the zeroes).

| Scenario | GSTIN | Bank selection | IFSC | Account holder override |
| --- | --- | --- | --- | --- |
| Approved | 29ABCDE1234F4ZT | ICICI Bank | ICIC0001234 | None |
| Pending | 29ABCDE1234F5ZS | Axis Bank | UTIB0001234 | None |
| Rejected | 29ABCDE1234F6ZR | ICICI Bank | ICIC0001234 | Different Synthetic Person |

Run one case at a time and confirm the actual result before continuing. Repeating a previously approved or active GSTIN produces the expected duplicate rejection. Existing records are preserved; reset only when explicitly requested. Synthetic approvals confirm configured consistency checks and keep authenticity Not Verified.

## Repeatable verification

```sh
.venv/bin/python -m unittest discover -q
.venv/bin/python tools/create_browser_fixtures.py
.venv/bin/python tools/run_e2e_batch.py --manifest tmp/qa_inputs/three_case_manifest.json --output tmp/qa_runs/new_rehearsal --real-gemini
```

The runner uses isolated storage by default. Select a fresh output directory for a new batch. No email is sent. Live AI failures remain recorded and cannot count as a passing document test. `tools/testing_cases.py` contains the form data; metadata and reports stay outside the PDF-only folders.

The PDFs are included in source exports. Optional regeneration uses `tools/create_testing_pdfs.py` with ReportLab; ReportLab is an authoring dependency, not an application dependency. The candidate owns recording and submission. Public hosting is not assumed; the process-access arrangement remains separate from a source repository.
