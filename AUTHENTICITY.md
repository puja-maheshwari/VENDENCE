# Document authenticity and approval scope

VENDENCE separates submitted fields, AI extraction, deterministic consistency checks, and recorded independent verification. A plausible GST certificate made in Word can match every field. It remains `NOT_VERIFIED` until an authorized person records a supported independent process. The AI never chooses approval or marks authenticity Verified.

## Policies

`strict` is the default. Both GST and banking evidence require recorded independent verification. A Verified record contains the current document hash, application revision, method, reviewer, evidence reference, scope notes, and timestamp. Replacing a document or correcting an application invalidates the earlier revision's verification. Missing or changed evidence cannot retain a Verified display. All required checks must pass before approval.

`demo_consistency` is an explicit environment setting for synthetic demonstrations. The operator declares a synthetic-only workspace at startup using `--synthetic-consistency-demo` (or both `VENDENCE_APPROVAL_POLICY=demo_consistency` and `VENDENCE_SYNTHETIC_DATA_ONLY=1`). Vendors submit directly without a policy checkbox. The declaration is recorded in each run’s checks; setting the policy alone does not satisfy it. The authenticity requirement is visibly recorded as a policy exception; the document state remains `NOT_VERIFIED`. This policy can demonstrate an Approved business-consistency outcome without claiming that fictional government or banking records exist. It must never be used to onboard real payable vendors. A recorded `VERIFICATION_FAILED` still blocks this policy.

The recorded status, reasons and correction requirements appear in a result dialog immediately after submission, and remain available in Verification Center. No email service is configured or required.

An authorized reviewer changing an Approved application's evidence to Not Verified or Verification Failed withdraws approval atomically and records Pending, the reviewer, the updated check and the new decision. The prior approval remains audited. Verification Center shows the updated result. Resolve the evidence and re-run the rules before a new approval. Integrity is checked during processing/review rather than by a continuous background monitor.

## Authorized GST review

1. An authorized reviewer opens the official GST portal outside VENDENCE and checks the taxpayer's legal name, GSTIN, status, and relevant details. The official [Search Taxpayer guide](https://tutorial.gst.gov.in/userguide/taxpayersdashboard/Search_Taxpayer_manual.htm) requires CAPTCHA for pre-login searches. The person handles that themselves. This app does not bypass CAPTCHA or fabricate results.
2. A registry match establishes taxpayer-record consistency, not that the uploaded PDF is genuine. Obtain the original registration certificate through an authorized channel, or compare with the taxpayer's certificate obtained using their authorized GST login. See the official [certificate download guide](https://tutorial.gst.gov.in/userguide/taxpayersdashboard/View___Download_Certificates.htm).
3. Record `GST_PORTAL_AND_ORIGINAL` only after both checks. Retain sensitive evidence in an access-controlled location and enter a case reference in VENDENCE rather than full banking data, secrets, or a private login URL.
4. `TRUSTED_DIGITAL_SIGNATURE` means a qualified reviewer actually verified a PDF signature, signer trust chain, integrity, and applicable validity/revocation information using an appropriate verifier. VENDENCE does not implement cryptographic PDF signature validation. A signature-looking image does not qualify.
5. `AUTHORIZED_REVIEW` requires a documented independent verification process and evidence; it is not an override for missing/mismatching fields. The rules still run after the attestation.

The authorized [NIC GST details API](https://docs.ewaybillgst.gov.in/apidocs/version1.03/get-gstin-details.html) needs issued credentials and authorization. No registry API integration is configured in this demonstration.

## Authorized banking review

`BANK_CONFIRMATION` means the reviewer independently confirmed ownership/details with a trustworthy banking channel, using contact details obtained independently of the uploaded document. A matching account number, IFSC format, logo, scanned stamp, or AI bank-statement classification alone is insufficient. There is no bank API or penny-drop ownership verification configured. `AUTHORIZED_REVIEW` must document equivalent authorized independent evidence and its limits.

## Suspicious or ambiguous evidence

Infographics, GSTIN-only screenshots, unreadable files, incomplete identities, masked account numbers, and wrong document types require correction. Legal and trade names remain separate; fuzzy name similarity is not approval evidence. A legitimate proprietorship with different trade and legal names can require additional documented evidence. The app conservatively leaves this Pending rather than replacing the legal name with the trade name.

Look for missing/contradictory fields, signs of editing, and synthetic/template disclaimers during review. Visual suspicion can justify additional investigation; absence of such signs cannot prove authenticity. The supplied Word-to-PDF imitation is explicitly fictional and should never receive a real verification attestation.

## Access and limits

Reviewer actions require the separate reviewer password. These are recorded human attestations, not automatic government authentication. The public demonstration uses shared workspace access and synthetic data; it is not a multi-tenant identity system or production payment authorization service.
