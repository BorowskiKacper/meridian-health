# Practice-run reset

Use this prompt to put the Meridian demo back to a clean run of the scripted questions in `demo-prompt-cache.md`. Ask for this reset between practice runs.

```
Reset the Meridian clinic database so the scripted demo prompts in demo-prompt-cache.md can be practiced again. Use the clinic schema from backend/.env DATABASE_URL. Leave every other schema alone. Do not drop tables and do not run python -m app.bootstrap.

Match patients by these ids:

- Jane Doe 11111111-1111-4111-8111-111111111111
- John Roe 22222222-2222-4222-8222-222222222222
- Amy Lee 33333333-3333-4333-8333-333333333333
- Rosa Alvarez 44444444-4444-4444-8444-444444444441
- Marcus Chen 44444444-4444-4444-8444-444444444442
- Helen Okonkwo 44444444-4444-4444-8444-444444444443
- Daniel Brooks 44444444-4444-4444-8444-444444444444
- Priya Shah 44444444-4444-4444-8444-444444444445
- Samuel Wright 44444444-4444-4444-8444-444444444446
- Naomi Fischer 44444444-4444-4444-8444-444444444447
- Luis Ortega 44444444-4444-4444-8444-444444444448

The only transcripts in scope are these exact sentences.

Jane Doe
- Research: Why is Jane’s A1c rising, and what second agent fits her kidney function?
- Screenings: What screening gaps are still open for Jane?
- Document: Document that an SGLT2 inhibitor was discussed because her A1c is 8.4 and her eGFR is 56.

John Roe
- Research: Does John qualify for lung cancer screening with low-dose CT given his COPD and smoking history?
- Screenings: What screening gaps are still open for John?
- Document: Document that John again declined smoking-cessation medication and that low-dose CT was discussed.

Amy Lee
- Research: Is Amy’s iron deficiency resolved, and does her sister’s colon polyps change her screening?
- Screenings: What screening gaps are still open for Amy?
- Document: Document that Amy’s iron was stopped after her hemoglobin reached 13 g/dL and her ferritin reached 46 ng/mL.

General chat writes no clinic rows. Its three questions only need the workspace clear and a hard reload:
- At what age does the USPSTF recommend starting colorectal cancer screening?
- When is lung cancer screening with low-dose CT indicated?
- What A1c target is typical for most adults with type 2 diabetes?

Set email to vicchen199@gmail.com on all eleven patients above. Leave every other patient column as it is, including email_opt_in. Leave allergies, encounters, family history, coverage, appointments, documents, eligibility checks, and email_messages as they are, except where an approved suggestion from one of the nine patient sentences above updated a family_history row. Leave sms_messages rows in place. Leave requests, ai_suggestions, notes, conditions, medications, observations, and audit_log rows that are not tied to those nine sentences.

"Send the reminder now" is not one of the nine sentences. On one patient's chart it emails only that patient's scheduled reminders to vicchen199@gmail.com, and it marks those reminders sent. Put the reminder rows below back so that prompt can be practiced again. Rows listed as sent stay sent. Leave the email_messages rows that the send wrote.

Undo chart writes from those nine sentences before deleting the suggestion rows:

- Find requests for these three patients whose transcript is exactly one of the nine sentences.
- Find ai_suggestions whose request_id is one of those requests.
- For an approved suggestion with a target_id, on conditions, medications, observations, or family_history, write that suggestion's before fields back onto that target row.
- For an approved suggestion with no target_id, on conditions, medications, observations, or family_history, delete the inserted row for that patient that matches the suggestion's after fields. If more than one row matches, stop and report it. Do not guess.
- Delete notes whose source_suggestion_id is one of those suggestions. Seed notes have a null source_suggestion_id; leave those notes.
- Delete audit_log rows whose suggestion_id is one of those suggestions.
- Delete those ai_suggestions, then delete those requests.

Restore exactly one reminder_schedule row per name for Jane Doe, John Roe, and Amy Lee. Delete extra rows that share a name. If sms_messages.reminder_id points at a row you must delete, set that reminder_id to null and keep the sms_messages row. For the eight panel patients, update due date and status only. Do not add or delete their reminder rows.

Jane Doe
- Colorectal cancer screening, due 2026-10-01, status scheduled, rule baseline_age 45, guideline_source_id uspstf:colorectal-cancer-screening
- A1c recheck, due 2025-12-09, status sent
- Diabetic eye exam, due 2026-03-01, status sent
- Mammography, due 2026-05-01, status sent
- Influenza vaccine, due 2026-10-15, status scheduled

John Roe
- Lung cancer screening, due 2026-11-01, status scheduled
- Colorectal cancer screening, due 2026-06-01, status scheduled
- Influenza vaccine, due 2026-10-15, status scheduled

Amy Lee
- Follow-up labs, due 2026-09-01, status scheduled
- Cervical cancer screening, due 2027-04-01, status scheduled

Rosa Alvarez
- Blood pressure check, due 2026-11-18, status scheduled
- Influenza vaccine, due 2026-10-20, status sent

Marcus Chen
- A1c recheck, due 2026-11-13, status scheduled
- Diabetic eye exam, due 2027-02-01, status scheduled

Helen Okonkwo
- Colorectal cancer screening, due 2026-10-30, status sent
- Mammography, due 2027-01-15, status scheduled

Daniel Brooks
- Influenza vaccine, due 2026-10-15, status scheduled

Priya Shah
- Cervical cancer screening, due 2029-05-14, status scheduled

Samuel Wright
- Colonoscopy surveillance, due 2028-06-01, status scheduled

Naomi Fischer
- Mammography, due 2026-11-01, status sent
- A1c recheck, due 2027-05-27, status scheduled

Luis Ortega
- Lung cancer screening, due 2027-03-01, status scheduled
- Influenza vaccine, due 2026-10-15, status sent

Keep Jane’s A1c recheck, Diabetic eye exam, and Mammography at status sent. Keep Rosa’s Influenza vaccine, Helen’s Colorectal cancer screening, Naomi’s Mammography, and Luis’s Influenza vaccine at status sent. Do not add or delete reminder rows. If a panel patient has a reminder name that is not in this list, stop and report it.

Clear chat history that would reappear in the window. The desktop transcript is browser memory, so a hard reload empties it. A paired phone replays workspace_jobs into the window on connect. For each workspace, delete workspace_events whose job_id is set, delete workspace_chunks owned by those jobs, delete the workspace snapshot chunk, then delete the workspace_jobs. Keep the workspaces row, including phone_hash, so the phone stays paired. Reset that workspace’s sequence and desktop_cursor to 0.

Then confirm: the reminder list above; all eleven patients have email vicchen199@gmail.com and their previous email_opt_in; no requests remain for those nine sentences; no notes remain whose source_suggestion_id pointed at those suggestions; workspace_jobs is empty. Tell me to hard-reload the chart.
```
