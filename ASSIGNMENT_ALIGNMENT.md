# Zamp PS-2 assignment alignment

Updated 19 October 2026 for in-app vendor communication and the simplified interface. The seven-page guide was read in full during the prior audit and PS-2's wording was rechecked for this change. Requirements in the guide are evidence, not authorization to contact or publish externally.

| Guide section | Implementation / status |
| --- | --- |
| Page 1: operational process and real inputs | Actual form/files -> Gemini extraction -> deterministic checks -> stored status and reasons |
| Page 1: Day-1 selection email | PS-2 selected; whether the candidate sent their choice remains unverified |
| Pages 1-2: runnable process and video links | Local process runs; accepted reviewer-access arrangement remains unsettled; candidate video is deferred |
| Page 2: intuitive UI/live stages | Existing four sections and pink/lavender/purple design; actual processing stages; result dialog after submission |
| Page 2: history/status/output dashboard | Overview, Registry, original document previews, checks, revisions and audit |
| Page 2: <=5-minute narrated video | Plan in DEMO.md; candidate records it later, happy path plus at least one edge, no slides |
| Page 3: PS-1 | Read; not selected. Invoice fixtures test wrong PS-2 evidence |
| Page 4: complete, consistent, credible vendor information | Mandatory fields/documents; India/GST formats/checksum; content classification; conservative legal/banking comparisons; separate authenticity policy |
| Page 4: Approved/Pending/Rejected with reasoning | All requirements pass -> Approved; supplied invalid GSTIN/email/IFSC/account format or active/approved duplicate -> Rejected; missing/ambiguous/technical/unverified strict evidence -> Pending |
| Page 4: communicate what is needed if not approved | Immediate status/reason/check dialog, persistent saved details, and correction/resubmission route. Email is not explicitly prescribed by the guide and has been removed at the user's instruction |
| Page 4: 2-4 meaningful edges | Wrong document/correction, bank mismatch, approved duplicate, fabricated certificate or invalid GSTIN; additional technical cases tested |
| Page 5: PS-3 | Read; not selected |
| Page 6: process map, judgment, deliberate AI | WORKFLOW.md maps actual stages; AI extracts and deterministic rules decide; chosen scope/limits documented |
| Page 6: prepare and rehearse actual runs | Synthetic inputs and sequence prepared; current regression/integration results in VERIFICATION.md; candidate rehearsal remains recommended |
| Page 7: ambiguity/assumptions | India/GST scope and strict versus synthetic policies documented; no fabricated verification claims |
| Page 7: any independent stack | Python/Streamlit/SQLite/Gemini; no Zamp/Pace dependency |
| Page 7: synthetic PS-2 forms/JSON allowed | Fictional realistic forms/documents included |
| Page 7: visible status/output, candidate logistics | Dashboard and result views implemented; extensions/interview/debrief are not software completion claims |

## Communication boundary

The vendor receives feedback while using the local application. The result is available after dismissing the dialog and can be reopened using its ID. This is not proactive contact after the vendor leaves, and IDs are navigation rather than remote authentication. No external portal or sending service is claimed.

## Verification and outstanding actions

See VERIFICATION.md for the current executed tests. Prior dated reports retain historical evidence; their mail-dependent behavior has been superseded. The user-authorized fresh reset preserved the prior database/uploads in a verified local recovery checkpoint. The active registry now contains the fresh synthetic test batch; corrections retain its original uploads, decisions and audit history.

The remaining candidate-owned actions are to rehearse, record their own <=5-minute video when ready, confirm any required choice email, and arrange the requested process/video links. No public hosting, source publication, recording or coordinator communication was performed.
