# Round: product and clinical recommendations

This document reviews the merged product (the `web` workspace, the FastAPI
backend, and the design notes in `system-design-graph.md`,
`system-design-routing-2.md` and `builder-contracts.md`) and recommends how to
move it from a strong hackathon demo toward an EMR that clinicians would choose
over what they have. It is written for the team, so it names files and tables
where a recommendation touches them.

The recommendations are grouped the way the team framed the ambition: what we
show doctors, the tabbed workspace, the 3D body model and analytics, the
database engine, and agent integration. A prioritised roadmap and a list of open
decisions close the document.

---

## 1. Where the product stands

What already works and is worth protecting:

- Approval is the only writer to the chart. `services/approval.py` applies
  allowlisted `before`/`after` diffs from `ai_suggestions`; nothing an agent
  says changes a record until a human approves it. This is the single most
  important design decision in the codebase and it is correct.
- Evidence has tiers (`baseline`, `guideline`, `literature`, `chart`, `payer`,
  `web`), web sources cannot back a chart change, a reminder change must cite a
  baseline source, and `verify_claims` runs a second pass over the answer. That
  is a stronger safety posture than most shipping "AI scribe" products.
- Identifiers are stripped before any evidence search (`_IDENTIFIERS` in
  `agents/doctor/__init__.py`, plus `evidence/guard.py`). WhatsApp reminders
  carry no PHI.
- The workspace metaphor (tabs per patient view, an assistant beside them, a
  body model as the primary chart surface) is genuinely different from a
  conventional EMR and is the right bet.
- The visual language (jade on ivory, serif headings, hairline rules, plenty of
  whitespace) is calm. Clinicians spend four to six hours a day in the EMR;
  calm matters.

Where it falls short of clinical use today:

- There is no allergy table. An EMR that cannot show allergies cannot be used
  for prescribing or ordering. This is the first thing to fix.
- Time is fake in the UI. The body and timeline tabs run on a 0–100 "minute"
  scale with labels like "18 months ago" (`whenLabel` in `web/lib/data.ts`).
  The backend has real `observed_at`, `onset_date` and `occurred_at` columns.
- Observations are shown as a single current value (`Region` tab). There are
  no trends, reference ranges or deltas, which is where most clinical signal
  lives.
- Only three chart regions map to atlas structures (`ATLAS` in
  `web/lib/chart.ts`: heart, lung, colon). `body_regions.mesh_name` exists in
  the schema but is not used to drive the mapping.
- The chart model is not configured (`agents/doctor/model.py` raises), so
  requests, research and approvals (which trigger the reminder agent) fail on
  the live server. `labs.extract_analytes` returns an empty list.
- Authentication is an `X-Role` header. Coverage, eligibility checks and
  appointments exist in the database but are not surfaced in the web app.
- The timeline-oriented database features the design notes describe
  (hypertables, continuous aggregates, vector search over notes) are not yet
  used. `notes.embedding` is a 768-dim vector column with no index and no
  writer.

---

## 2. Design principles for the clinician

Everything below follows from a few facts about how clinicians work.

**The first ten seconds decide the visit.** Before a doctor says a word they
need: who this is (name, age, sex, photo), why they are here, what could kill
them (allergies, anticoagulation, code status, critical results), what changed
since last time, and what is due. If the UI makes them hunt for any of these it
has failed before the encounter starts.

**Burnout is an information-design problem.** Note bloat, alert fatigue and
"pajama time" (charting after hours) are the top complaints in every physician
survey. Every surface should be judged on whether it reduces clicks, reduces
reading, and reduces re-typing. An agent that drafts and a human who approves
is exactly the right division of labour, but only if approving is faster than
doing.

**Wrong-patient actions are a patient-safety event.** Tabbed interfaces make
this easier to get wrong, not harder. Every tab, card and approval must carry
the patient's identity, and the design should make it visually obvious when
two patients' tabs are open at once.

**Clinicians trust what they can verify.** The citation and evidence-tier work
in the backend is the right instinct. The UI needs to show it as something
clinicians recognise (a grade, a source, a date) and never as raw tier strings.

**Show the trajectory, not the point.** A creatinine of 1.3 means nothing
without the last three values. A1c, eGFR, LDL, weight, blood pressure: these
are curves, not numbers.

---

## 3. What we show doctors, surface by surface

### 3.1 Patient banner (new, persistent)

Add a slim banner above the tab content that is always visible for the active
patient, regardless of tab:

- Name, preferred name, age, sex, DOB, MRN, photo or initials.
- Allergies with severity (anaphylaxis in red; "No known allergies" is an
  explicit, recorded statement, not an empty list).
- Code status and advance directive flag when recorded.
- Active problem count, active medication count, pending approvals count
  (each clickable to the relevant tab).
- Next due item from `reminder_schedule`.
- Coverage status from `coverages.active` and whether a prior auth is on file.

This needs a new `allergies` table (substance, reaction, severity, onset,
source, verified_by) and an `allergies` list in `get_patient_context` so the
agents see them too. Nothing the chart agent proposes about medication should
reach `propose_change` without the allergy list in its context.

### 3.2 Body tab

Today: a 3D model, a specialty filter, a fake-time slider and a findings list
with severity dots.

Recommendations:

- Replace the 0–100 `minute` slider with a real date axis derived from the
  oldest and newest chart event. Show tick marks for encounters. Keep the
  "scrub through time" interaction; it is one of the product's best ideas.
- Add a "since last visit" toggle that highlights only structures with new or
  changed findings. Clinicians think in deltas.
- Group the findings list by body system (cardiovascular, respiratory, GI,
  renal, musculoskeletal) rather than one flat list sorted by time, and let the
  specialty filter act on those groups. Use `specialty_focus` from the database
  to drive this instead of hardcoding specialties on the client.
- Encode more than severity on the mark. A small sparkline or arrow (rising,
  stable, falling) next to each lab-type finding tells the doctor whether to
  look closer.
- Make the measure and mark tools persist. A measurement (wound length, oedema
  circumference, lesion diameter) taken on the model should become an
  `observations` row with a body region and a date, so the next visit can
  compare. Marks should become pending suggestions, not ephemeral annotations.
- Provide laterality and bilateral structures as first-class regions. The atlas
  distinguishes `kidney_l` from `kidney_r`; the chart region keys should too.
- Add a 2D fallback (anterior/posterior body outline with the same marks) for
  low-powered devices, accessibility, and printing. The 3D scene should be an
  enhancement, not a requirement to read the chart.
- Show the atlas's Latin name and a one-line lay description on hover for
  patient-facing explanations. Doctors use the body model to explain things to
  patients; make that a deliberate mode (hide MRN, hide pending suggestions,
  larger type).

### 3.3 Timeline tab

Today: findings and notes grouped by a coarse label, newest first.

Recommendations:

- Group by encounter, with the encounter type and summary from `encounters` as
  the header, and labs, medication changes, notes and procedures as rows
  beneath it. Encounters are how clinicians remember a chart.
- Add swim lanes: Problems, Medications, Labs, Encounters, Communications
  (reminders sent, STOP received). A medication lane that shows start, dose
  changes and stop as a bar rather than as discrete rows is immediately
  readable.
- Overlay medications on lab trends. "Started atorvastatin here; LDL fell from
  190 to 110 over the next two panels" is the kind of view no mainstream EMR
  does well and the schema already supports (`medications.start_date`,
  `observations.observed_at`).
- Filters by kind, by body region (clicking a region in the body tab should
  open the timeline pre-filtered) and by source (clinician, uploaded document,
  agent-approved).
- Pending suggestions are correctly excluded; show a small count ("3 pending
  changes not shown") linking to Approvals so nobody thinks the timeline is
  complete.

### 3.4 Region tab

Today: one finding, its observations as label/value pairs, medications, family
history, notes.

Recommendations:

- Turn each observation into a trend chart with the reference range as a
  shaded band and the current value marked. Reference ranges should come from
  the lab document when available and from a terminology table otherwise.
- Show the related problem's full history: onset, status changes, who recorded
  them, which encounters touched it.
- Show medications that act on this region with indication, start date, last
  reconciled date, and adherence signals (refill gaps if pharmacy data is ever
  integrated).
- Show cross-region implications. Diabetes on the pancreas should surface the
  kidney (eGFR, UACR), the eyes (retinal exam due), and the feet (foot exam).
  This is a table of condition to related region and screening, which the
  reminder rules are already halfway to describing.
- Link the relevant guideline statement for the condition (USPSTF, ADA, KDIGO,
  ACC/AHA) with publication date. Clinicians want the source one click away,
  not a paraphrase.
- Offer an "Ask about this" button that opens the agent with the region's
  context already attached, so the question is grounded without re-typing.

### 3.5 Approvals queue

Today: pending and decided action cards with before/after and a plain-text
footer joining source, confidence and citations; an "Approve all" button; an
audit list.

Recommendations:

- Remove "Approve all" for chart changes. Bulk approval of medication or
  problem-list edits is how an automation error becomes a chart error. Allow
  bulk approval only for low-risk kinds (opening tabs, running searches) and
  make chart changes one at a time with the diff in view.
- Render the diff per field rather than as two strings. For a medication
  change, show dose, route and frequency as separate rows with the changed
  cells highlighted.
- Show evidence as badges with human labels: "USPSTF 2021", "Chart (lab,
  2024-03-01)", "Literature (PubMed, 2019)". Make each badge open the source.
  Order badges by tier so the strongest evidence is first.
- Show confidence as a calibrated phrase ("high", "moderate", "low") with the
  number on hover, and show `validation_flags` from `ai_suggestions` as
  warnings rather than hiding them.
- Show what `verify_claims` could not confirm. If the second pass hedged or
  dropped a sentence, the reviewer should see that the original claim was
  weakened and why.
- Add "Edit then approve". The most common clinician reaction to a draft is
  "almost right"; forcing reject-and-redictate wastes the work.
- Add undo with a window (for example, the same session) that writes a
  compensating suggestion through the same approval path, so the audit trail
  stays linear.
- The audit log needs actor, role, timestamp and the suggestion id. Right now
  the UI shows action and detail only; the `audit_log` table has more.

### 3.6 Reminders tab

Today: a list of schedule rows with status labels, a demo "run reminders"
button, and STOP handling.

Recommendations:

- Show why each reminder exists: the rule name, the guideline source
  (`reminder_rules.guideline_source_id`), the baseline age, and any adjustment
  the agent proposed (for example, colorectal screening moved to 40 because of
  a first-degree relative at 50). The adjustment is the differentiator; make it
  visible.
- Show the communication history per reminder from `sms_messages`: sent,
  delivered, replied, STOP. Record consent (`sms_opt_in`) with a date and
  channel; TCPA and most state laws expect that.
- Separate patient-facing reminders (screening due) from clinician-facing tasks
  (review result, sign note, respond to prior auth). The product currently
  blends them.
- Panel view: all patients with a reminder overdue, grouped by rule. This is
  the first step toward quality-measure reporting (HEDIS, MIPS), which is what
  practices are paid on.

### 3.7 Lab document tab

Today: upload, a reply from the backend, and a table of extracted rows when
there are any (currently none).

Recommendations:

- Side-by-side verification: the source image on the left with extracted
  values on the right, each extracted value highlighting its bounding box on
  hover. Human-in-the-loop extraction only works if the human can check it
  quickly.
- Structured analytes with LOINC code, value, unit, reference range, collection
  time and the flag the lab printed. Normalise units before storing in
  `observations`.
- Delta flags against the patient's own prior values, not just the lab's
  population range. A creatinine within range that doubled since last year is
  the finding.
- Auto-pin each extracted analyte to its body region (ALT to liver, creatinine
  to kidney, A1c to pancreas) as pending suggestions, so the body tab lights up
  after approval. The web `data.ts` fixtures already imagine this
  (`altLab`, `creatinineLab`); make it real.
- Treat uploaded documents as untrusted input to the model. A PDF can contain
  text intended to steer the extractor. Strip and sandbox before prompting,
  and never let extracted text become a tool call.

### 3.8 Research tab and agent window

Today: a question, an answer, citations as strings; the agent window shows a
conversation with proposal cards inline.

Recommendations:

- Distinguish chart facts from literature in the answer. Two columns or two
  colours: "From this chart" and "From the evidence". Clinicians need to know
  which sentences are about this patient.
- Render citations as cards with title, source, year, tier badge and a link.
  Show the search query that was sent (already de-identified) so the clinician
  can judge whether the search was the right one.
- Stream the answer; a clinical question that takes eight seconds with no
  feedback will be abandoned.
- Keep the conversation attached to the patient and the tab it was asked from,
  and let it be saved to the chart as a note (through approval) when the
  clinician wants it.
- Add voice properly. The backend already has `channel == "voice"` and
  `spoken_text`; the product should let a clinician dictate at the bedside and
  review proposals on the way back to the desk.

### 3.9 Views that do not exist yet and should

In rough order of clinical necessity:

1. Allergies (see 3.1).
2. Medication list with reconciliation, interaction and allergy checks before
   any medication suggestion reaches the queue.
3. Problem list (active, resolved, chronic) as the index into the body model.
4. Vitals flowsheet with growth or trend charts.
5. Results inbox: new observations and documents the clinician has not yet
   acknowledged, with one-click "reviewed" that writes to the audit log.
6. Encounter note editor with SOAP or APSO structure, drafted by the agent from
   the conversation and dictation, signed by the clinician.
7. Schedule and patient roster (`appointments` exists in the schema). The
   workspace today assumes you already know which patient you want.
8. Coverage and eligibility (`coverages`, `eligibility_checks` exist). The
   secretary agent's output needs a home where front-desk staff see it.
9. Orders (labs, imaging, referrals) drafted by the agent, signed by the
   clinician, with the prior-auth note from eligibility attached.

---

## 4. The tabbed workspace

Tabs are the right container, but a browser metaphor applied to patients needs
guard rails.

- Group tabs by patient with a visible boundary and a patient colour or
  initials pill on every tab. When two patients are open, the active patient's
  group should be unmistakable. The current strip shows a surname in small
  grey type; that is not enough.
- Keep the patient banner (3.1) pinned above the content area and change it
  with the active tab, so the identity is always next to the data.
- Add split view: two tabs side by side, typically Body and Region, or
  Timeline and a lab trend. The `layout` state already has three modes; a
  fourth that holds two tab ids is a small change with a large payoff.
- Pin tabs (Approvals and the current patient's Body are natural pins) and
  restore the tab set per user per patient on return.
- Deep links: every tab should have a URL (`/patients/:id/body`,
  `/patients/:id/region/:findingId`) so the agent can propose "open this" as a
  link and so links can be shared between clinicians.
- Keyboard first: Ctrl/Cmd+1..9 to switch tabs, Ctrl/Cmd+W to close,
  Ctrl/Cmd+K for a command palette that searches patients, tabs and agent
  actions. The body tab already has single-key shortcuts; extend the habit.
- Role-based default tab sets: the doctor opens to Body, Approvals and the
  results inbox; the front desk opens to Schedule, Eligibility and Reminders.
- Agent-opened tabs should be marked as such until the clinician interacts
  with them, so the clinician can tell what they chose from what was proposed.
- Cap the number of open tabs per patient softly (collapse into an overflow
  menu) rather than letting the strip scroll out of view.

---

## 5. Data visualisation beyond the body

The body model is the entry point; the analytics behind it are what make the
product clinically useful.

- Lab trend charts with reference bands, medication start/stop markers, and
  the ability to overlay two analytes (eGFR and UACR; A1c and weight).
- Risk scores computed from chart data with full transparency: ASCVD 10-year
  risk, CHA2DS2-VASc, KDIGO heat map (eGFR against albuminuria), FRAX, CURB-65
  where applicable. Show the inputs used and which ones are missing or stale.
  Never show a score the chart cannot fully support without saying so.
- Care-gap view per patient: which guideline-recommended screenings, vaccines
  and monitoring labs are missing, each with the source. This is the reminder
  agent's reasoning made visible before it proposes anything.
- Panel analytics for the practice: patients with A1c above target, overdue
  colorectal screening by age band, hypertension control rate, and the body
  model as a heat map of where the practice's active problems cluster. This is
  where TimescaleDB continuous aggregates earn their place.
- Medication adherence and polypharmacy view: count of active medications,
  anticholinergic burden, duplicate therapy, and interaction flags.
- Document viewer with annotations, linked to the observations extracted from
  it.
- Patient-facing mode of the body tab (see 3.2) for shared decision making.

Design constraints for all of these: the number comes with its date, its
source and its range; colour means the same thing everywhere (the existing
critical/watch/clear vocabulary is good; keep it and define it in one place);
and every chart can be printed or exported as an image for a referral letter.

---

## 6. Database engine

The schema in `backend/app/db/models.py` is a sound clinical core: patients,
conditions, medications, family history, documents, observations, encounters,
requests, suggestions, notes, body regions, specialty focus, reminder rules and
schedule, audit log, SMS messages, coverages, eligibility checks, appointments.
The design notes name Tiger/Timescale and pgvector; the code uses plain
Postgres tables with `STORAGE PLAIN` and no indexes beyond primary keys.

Recommendations, in order:

1. **Add the missing clinical tables.** `allergies`, `immunizations`,
   `procedures` (today they are `encounters` with a type), `vitals` (or a
   typed view over `observations`), `orders`, `care_team`, `consents`.
2. **Migrations.** Replace `Base.metadata.create_all` in `bootstrap.py` with
   Alembic. A clinical schema will change constantly and must be reproducible.
3. **Indexes.** Every `patient_id` foreign key, `(patient_id, observed_at)` on
   observations, `(patient_id, created_at)` on audit and requests,
   `(status, patient_id)` on suggestions and reminders.
4. **Hypertables.** Convert `observations`, `audit_log`, `sms_messages` and a
   future `vitals` table to Timescale hypertables partitioned on time. Add
   continuous aggregates for per-patient monthly lab summaries and per-panel
   care-gap counts. Enable compression on chunks older than a year. This is
   what makes the trend charts and panel analytics fast at scale.
5. **Vector search.** Add an HNSW index on `notes.embedding`, write embeddings
   when a note is approved, and implement `search_notes` as hybrid retrieval
   (Postgres full-text `tsvector` plus cosine similarity, fused by reciprocal
   rank). Embed documents too, chunked, with the chunk's bounding box kept for
   the verification view.
6. **Terminology.** Store codes alongside display names: ICD-10 and SNOMED CT
   on conditions, RxNorm on medications, LOINC on observations, CPT on
   procedures. Add a small `terminology` table (system, code, display) and
   reference it. Without codes, interaction checks, quality measures and
   interoperability are impossible.
7. **FHIR alignment.** Keep the internal schema, but add a mapping layer that
   exposes Patient, Condition, MedicationStatement, Observation, Encounter,
   AllergyIntolerance, DocumentReference and Appointment as FHIR R4 resources,
   and accept the same on ingest. SMART on FHIR is how hospitals will let this
   product in, and 21st Century Cures information-blocking rules expect a FHIR
   API.
8. **Append-only chart with versions.** The `before`/`after` discipline on
   suggestions is already an event log for agent changes. Extend it: every
   clinical row carries `version`, `valid_from`, `valid_to`, `recorded_by`, and
   `recorded_at`, and corrections create new versions. Clinicians and auditors
   need "what did the chart say on this date".
9. **Tenancy and access.** Row-level security keyed on organisation and on
   care-team membership. Break-the-glass access that is allowed but logged
   loudly. Column-level encryption for direct identifiers (`phone_e164`,
   `member_id`).
10. **Audit immutability.** `audit_log` should be insert-only at the database
    role level, with a periodic hash chain or export to write-once storage.
11. **Time zones.** All instants are already `timestamptz`; store the
    patient's and the clinic's zone so "this morning" in a lab report resolves
    correctly.
12. **Keep the test discipline.** The private-schema test harness is valuable.
    Extending it to hypertables and extensions needs care (the test schema
    must own its chunks); plan for that when adopting Timescale.

---

## 7. Agent integration

The architecture (route, draft, verify, propose, approve, audit) is right. The
gaps are configuration, breadth of tools, and how results are shown.

### 7.1 Make the current loop work end to end

- Configure the chart model and set up a fallback. `model.complete` has three
  task types (`classify`, `chart`, `research`, plus `reminders`); each should
  have a versioned prompt, a JSON schema for the output, and a test fixture.
- Build a golden set: twenty dictations and questions per route with expected
  suggestions, and run them in CI against recorded model outputs. Clinical
  agents regress silently without this.
- Log prompts, tool calls, model outputs and verification results per request
  id, with PHI redacted, so a suggestion can be explained after the fact.

### 7.2 Data querying

- Give the agent a semantic layer, not raw SQL. Define named, parameterised
  queries ("labs for patient over period", "patients overdue for rule",
  "medication changes since date") in `mcp/tools.py` and let the model fill
  parameters. If free-form SQL is ever allowed, run it under a read-only role
  with row-level security and a statement timeout, and show the SQL to the
  clinician.
- Query results should become tabs. "Show me her kidney function over five
  years" should open a Region or Analytics tab with the chart, not paste a
  table into the conversation. Add a `proposed_action` kind of `open_view`
  with a typed payload.
- Panel questions ("who on my panel is overdue for colorectal screening")
  route to the same semantic layer and open the panel view.

### 7.3 Clinical drafting

- Ambient encounter notes: from dictation or a recorded conversation, draft a
  SOAP note with each sentence linked to its source utterance, and propose
  problem-list, medication and order changes as separate suggestions. Signing
  the note approves nothing else.
- Pre-visit summary: the night before, draft a one-paragraph brief per
  scheduled patient (why they are coming, what changed, what is due) and show
  it in the roster. This is the "first ten seconds" from section 2, prepared.
- Inbox triage: classify new results as normal, abnormal-expected,
  abnormal-needs-action, and draft the patient message for the first two.
- Orders and referrals: draft the order, attach the eligibility summary and
  prior-auth note from the secretary agent, and queue it for signature.
- Medication safety: before any medication suggestion is stored, run an
  allergy check and an interaction check (a local RxNorm-based rules table to
  start) and attach the result as a validation flag.

### 7.4 Research

- Keep the tiered evidence model and make the tiers visible (3.8). Add
  guideline recency as a first-class property; a 2008 guideline is a different
  thing from a 2023 one.
- Add structured sources beyond USPSTF and PubMed: CDC immunisation schedules,
  FDA labels (DailyMed), ClinicalTrials.gov for eligibility questions, and the
  practice's own protocols as an indexed corpus.
- Patient-specific research: the agent should use the chart to constrain the
  question (age, sex, eGFR, pregnancy, allergies) and say which constraints it
  applied.
- Let the clinician save a research answer as a chart note or as a patient
  handout (through approval), and track which questions were asked most often
  across the practice to seed protocols.

### 7.5 Safety for agents specifically

- Prompt-injection defence for all document and message inputs (lab PDFs,
  patient SMS replies, external records). Treat them as data, never as
  instructions; never let extracted text reach a tool call unparsed.
- Hard rules the model cannot override: no web-tier citation on chart changes,
  no reminder change without a baseline citation, no medication change without
  an allergy check. These already exist in `propose_change`; keep adding at the
  same layer.
- Rate and scope limits per role. A secretary role should not be able to
  trigger chart suggestions.
- Show the model and prompt version on every suggestion card so a clinician
  can see when behaviour changed.
- Measure acceptance and edit rates per suggestion kind and per clinician.
  Falling acceptance is the earliest signal of a bad prompt change.

---

## 8. Compliance, trust and go-to-market constraints

These are not features, but they decide whether a clinic can run the product.

- HIPAA: a BAA with every vendor in the data path (model provider, Twilio,
  hosting, search providers). The de-identification before evidence calls is
  a strength; document it as a policy and test it.
- Authentication: replace the `X-Role` header with real identity (OIDC) and
  role-based access, with SMART on FHIR launch for hospital deployments.
  Session timeouts and device trust on shared workstations.
- Patient communication: record consent per channel with timestamp, honour
  STOP within the regulatory window (already done), and keep message content
  free of PHI (already done). Add HELP handling and a quiet-hours rule.
- FDA clinical decision support: stay on the non-device side of the CDS
  guidance by always showing the basis for a recommendation so the clinician
  can independently review it. The citation design supports this; the UI must
  surface it. Avoid language that reads as diagnosis ("has", "is") in favour
  of "suggests", "consistent with", with the evidence attached.
- ONC certification and information blocking: a FHIR API and patient access
  are prerequisites for US practices that bill Medicare.
- Accessibility: WCAG 2.1 AA for the web app, and the 2D body fallback so the
  chart is readable without WebGL.
- The 3D atlas licence (CPAL-1.0) and any data licence on its assets need a
  decision before a public or commercial release; this was deferred during the
  merge and remains open.

---

## 9. Prioritised roadmap

Ordered by clinical risk reduced per unit of work. Each item names the parts
of the codebase it touches.

**Foundations (make the demo truthful)**

1. Allergies table, context and banner (`db/models.py`, `mcp/tools.py`,
   `web/components/shell`, new banner component).
2. Real dates on the body and timeline tabs (`web/lib/chart.ts`, `data.ts`,
   `body-tab.tsx`, `timeline-tab.tsx`).
3. Observation trend charts in the Region tab with reference ranges
   (`region-tab.tsx`, a chart primitive, `GET /patients/{id}/regions/{key}`
   returning history, not just latest).
4. Patient identity on every tab and a split view (`workspace.tsx`,
   `store.ts`).
5. Configure the model, add golden tests, remove "Approve all" for chart
   changes (`agents/doctor/model.py`, `tests/`, `queue-tab.tsx`).
6. Drive the atlas mapping from `body_regions.mesh_name` so every region the
   backend knows is visible on the body.

**Clinical breadth**

7. Medication list with allergy and interaction checks before suggestions.
8. Lab extraction with side-by-side verification and auto-pinning.
9. Results inbox and encounter note editor with agent drafts.
10. Roster and schedule, eligibility surfaced for the front desk.
11. Alembic migrations, indexes, terminology codes.

**Scale and intelligence**

12. Timescale hypertables and continuous aggregates; panel analytics.
13. Hybrid note and document search with pgvector HNSW.
14. Semantic query layer and "query opens a tab".
15. Risk scores and care-gap view.
16. FHIR R4 read/write and SMART on FHIR launch; real authentication.

---

## 10. Decisions for the team

- Which specialty is the first customer? Primary care benefits most from the
  reminder and care-gap work; trauma and orthopaedics benefit most from the
  body model. The demo data (`Nora Ellison`, `Marcus Hale`) leans both ways.
  Choosing one sharpens every decision above.
- Is the body model the chart's primary index, or one view among several? The
  recommendations assume it is the primary index and that problem list,
  timeline and analytics are projections of it.
- How much agent autonomy is acceptable for low-risk actions (opening tabs,
  running searches)? The current design queues everything; auto-executing the
  genuinely harmless kinds would make the assistant feel faster without
  weakening the chart-write guarantee.
- Will the product own patient communication (SMS, portal), or integrate with
  an existing one? This determines how much of section 3.6 to build.
- Timescale and pgvector are both committed to in the design notes. Confirm
  the hosting target (Tiger Cloud, self-hosted Timescale, or plain Postgres
  with extensions) before the hypertable work, since it affects the test
  harness.
- Atlas licensing (section 8) and whether the vendored atlas stays in this
  repository or becomes a dependency.
