# Meridian: product and clinical recommendations

> **Frontend planning update, 2026-10-10:** The current hackathon priorities
> are in sections 9, 11, 12, and 13. Section 13 maps the UI to the current backend
> and expands the clinical and diagnostic data roadmap. Section 11 adds the proposed demo story, clinical
> display rules, implementation boundaries, and acceptance criteria. Sections
> 2–8 remain a longer-term product backlog; they are not a commitment to build
> a complete EMR during the hackathon. Recommendations are proposals unless
> explicitly marked implemented in the status below.

## Status as of 2026-10-10

The frontend and backend are merged on `main`. Meridian branding and assistant
contrast are committed locally, with the next clinical-workspace refactor in
progress. The team chose primary care as the first setting. The gap-closing
work below is partly done; the rest remains a backlog. See section 13 for the
latest implementation boundaries; older status bullets describe earlier passes.

### Done

- **Structured clinical overview.** The default chart opens on an overview
  with encounter and appointment dates, paired blood-pressure curves, weight
  history, active problems, medication records and lab trends. Narratives are
  expandable context. Anatomy is a separate optional view. Problems,
  medications, allergies, vitals and follow-up are directly accessible from
  the persistent patient banner.
- **Measurements and provenance.** Trend points retain dates, units, source
  and document identifiers. Graphs support keyboard point inspection and exact
  values tables. Missing records and single measurements are explicit; unlike
  units are not plotted on a shared axis. Generic display thresholds no longer
  become red critical flags or unlabeled treatment-target bands. The anatomy
  filter is labeled "Findings recorded by" because it does not reconstruct a
  complete historical chart. Timeline years now appear newest first.
- **Clearly synthetic demo vitals.** Optional `app.bootstrap --demo-vitals`
  adds missing weight, pulse and blood-pressure examples only for the three
  named demo patients. The source is `demo_vitals`, displayed as "Synthetic
  demo vitals". Existing observations and original encounter dates are
  preserved. Re-running the seed does not duplicate data. The local demo has
  32 added records; this is example data, not inferred clinical history.
- **Visual consistency pass (2026-10-10).** The chart and assistant now share
  panel framing, corner radii and a muted green palette. A single application
  header replaces separate branding. Patient identity, demographics and
  allergies occupy a dedicated row; chart counts and follow-up occupy the
  row below, eliminating the diagonal wrapping around the patient's name.
  Counts now open dedicated problem and medication lists. Amber and red
  remain reserved for clinical meaning.
- **Spacing and responsive presentation.** The overview uses a single patient
  identity banner, calmer typography, consistent page gutters and a grid
  driven by available chart width. The anatomy stage scales to viewport
  height. The assistant has explicit patient context, visible suggested
  actions and a simpler composer. Narrow screens use a dismissible assistant
  drawer. Keyboard focus and secondary-text contrast are stronger. This is a
  visual pass; the visit workflow, source provenance and clinical interpretation
  work proposed in section 11 remains open.
- **One place to change the workspace view.** The application header has one
  View menu: Split view, Chart full screen, and Assistant full screen. It
  replaces the separate show/hide, maximize and move-to-tab controls. The
  assistant always uses its green surface; conversation tabs can no longer
  become white chart tabs. Switching views preserves the conversation and
  unsent draft. Conversation-close icons were removed to avoid confusing
  deletion with hiding the assistant. Contextual chart questions still open
  the same assistant, and assistant navigation reveals the requested chart.
- **Allergies.** New `allergies` table (`backend/app/db/models.py`), repository
  functions, seed rows (Jane: penicillin and shellfish; John: verified NKDA;
  Amy: sulfonamides), and `allergies` added to `get_patient_context` so every
  agent draft sees them. Tests in `tests/api/test_body.py` and
  `tests/mcp/test_patient_tools.py`.
- **Full chart endpoint.** `GET /patients/{id}/chart`
  (`app/services/chart.py`, `app/api/routes/body.py`) returns the patient with
  real dates, regions with their specialties, conditions, medications,
  observation series grouped by analyte, encounters, notes, reminders with the
  rule and guideline source, appointments, coverage and the pending count.
  `GET /patients` now also carries `date_of_birth` and `allergies`.
- **Primary care demo data.** `backend/seed/seed.py` stays the base contract
  the existing tests pin. `backend/seed/demo.py` layers depth on top and
  `app/bootstrap.py` runs both, so the live clinic has: nine body regions,
  a `primary_care` specialty focus, Jane's diabetes and CKD with A1c, eGFR,
  creatinine, UACR and blood pressure series, office visits, and care-gap
  reminders. Verified by `tests/db/test_demo_seed.py`. The clinic schema was
  reseeded; the API serves the new data.
- **Web reads the chart.** `web/lib/chart.ts` loads each patient from the chart
  endpoint instead of three specialty calls plus per-region fetches. Findings
  carry trends, problems and real onset dates; the anatomy filter uses a real
  date axis (`Findings recorded by`, spanning the oldest event to today).
  Active problems and display thresholds prompt review without implying an
  explicit critical-result flag. Atlas placement
  comes from `body_regions.mesh_name` via `web/lib/atlas.ts` (pancreas, kidney,
  liver, thyroid, breast, cervix added).
- **Region tab.** Recorded-value trend charts with medication
  start markers on the curve, problem status with onset, medication history,
  a "look at together" section (diabetes links kidney and heart) and an
  "Ask about this" button that opens the agent with the region attached.
  Generic thresholds in `web/lib/reference.ts` are not source-specific lab
  ranges or individualized goals and are no longer displayed as such bands.
- **Timeline tab.** Real dates, grouped by year, with visits, procedures,
  medication starts and notes as distinct kinds, plus a problem list that
  opens the region.
- **Care gaps.** The reminders tab leads with open gaps (overdue or reminded
  but not scheduled) and shows the guideline source and baseline age per rule.
- **Patient banner.** Persistent above every tab: initials, patient selector,
  age, recorded sex, date of birth and a demo record identifier (`R-` plus six
  characters). A compact allergy summary opens the full substance, reaction,
  severity, status and recorded-date table. Links open dedicated problem,
  medication, trend and follow-up views. Coverage is secondary overview detail.
  Empty allergy data remains distinct from recorded NKDA. Each tab carries patient
  initials and a surname with a muted green accent.
- **Approvals.** "Approve all" no longer appears when any pending item is a
  chart change, in both the queue and the conversation.
- **Colour.** Jade is the application surface (`--background` is jade-50); white
  is reserved for the chart page. The agent window is deep jade with ivory text
  (scoped under `.agent-window` in `web/app/globals.css`). It retains this
  appearance in both split and full-screen views.
- **Backend tests: 246 pass. Web `tsc --noEmit` and eslint are clean.**

### Verified in the browser

The structured chart pass was verified in headless Microsoft Edge against the
local clinic API: correct blood-pressure and weight values and sources,
keyboard point inspection, exact-value tables, stopped-medication history,
allergy reaction/severity, explicit NKDA, switching among all three patients,
lab graphs and date filters. The anatomy view remains available separately;
its date slider is accessible. Timeline years display newest first. Chart
layouts passed at 1600, 1366, 768, 390 and 320 pixels without horizontal page
overflow. Browser fixtures also checked unknown sex, missing allergies and
weight, and a single systolic reading without an invented diastolic component
or trajectory. Four frontend clinical-data tests and two isolated database
seed tests passed. ESLint and TypeScript passed. Model-backed writes remain
outside these checks.

The visual consistency pass was checked locally in headless Microsoft Edge
against the running frontend and clinic API. Verified the 1366 × 900 laptop
layout (matching panel boundaries and radii, anatomy toolbar visible), plus
1600, 768, 390 and 320-pixel widths without horizontal page overflow. Checked
assistant hide/show/full-screen, timeline, approvals, region details and
switching to Jane's chart. No browser exceptions or failing HTTP responses
occurred in these checks. ESLint, TypeScript and `git diff --check` passed.
This verification did not exercise model-backed requests or chart writes.

Earlier merged-branch checks used headless Chrome, with screenshots in
`/opt/cursor/artifacts/`:

- `body-jane-doe.png`: Jane's banner with Shellfish and Penicillin, three
  regions pinned on the model (heart, pancreas, kidney), trend arrows and
  values beside each, the dark agent panel beside the white chart.
- `region-diabetes-trends.png`: A1c chart, 7.9 down to 7.1 then up to 8.4,
  goal band below 7%, metformin start marked, latest point in red.
- `timeline.png`: real dates grouped under 2019–2025, lisinopril, metformin,
  atorvastatin starts, the colonoscopy, visit summaries.
- `care-gaps.png`: Amy's overdue follow-up labs with the USPSTF source line.
- `agent-contrast.png`: a sent message and the agent's reply on the dark panel.

### Known issues found while verifying

- The 3D scene labels overlap. Jane's heart carries both "Hypertension" and
  "Chronic kidney disease, stage 3a" because the kidney finding sorts first and
  the scene places the active label by list order rather than by the clicked
  structure. The kidney mark itself sits low, over the abdomen. Label placement
  in `web/components/body/scene/` needs work before this view is shown to anyone.
- Breast and cervix map to surface regions (`regions.mammary_region_l`,
  `regions.hypogastric_region_l`) because the atlas is a male model and has no
  mesh for them. Noted in `web/lib/atlas.ts`.
- The chart model is still unconfigured, so requests, research and approvals
  fail and roll back. Lab extraction still returns no analytes.
- Reference ranges are adult defaults hardcoded in `web/lib/reference.ts`, not
  per-patient or per-lab.

### Still open across the product

This is an inventory, not the frontend team's execution order. Use section 9
for the hackathon sequence; backend dependencies should be coordinated with
their owners rather than expanding the frontend team's scope.

1. Wire and evaluate the chart model (section 7.1). Blocks everything agent-side.
2. Medication list with allergy and interaction checks before any suggestion.
3. Lab extraction with side-by-side verification and auto-pinning to a region.
4. Results inbox and the encounter note editor.
5. Roster and schedule view; eligibility surfaced for the front desk.
6. Alembic migrations, indexes, terminology codes (ICD-10, SNOMED, RxNorm, LOINC).
7. Timescale hypertables and continuous aggregates; panel analytics.
8. Hybrid note and document search on the pgvector column.
9. Semantic query layer where an answer opens a tab.
10. Risk scores and the care-gap view across the whole panel.
11. FHIR R4 and real authentication. `X-Role` is still the only access control.
12. The 3D label placement bug above, and the atlas licence decision.

---



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

Where it falls short today, checked against integrated commit `4800a40`:

- Allergies, real chart dates, trends, nine atlas mappings and a persistent
  patient banner are implemented. Their earlier absence is no longer work
  to schedule. The remaining gaps are interpretation, workflow and fidelity.
- The date slider filters which findings appear, but findings retain current
  summaries and latest values. It is not a reconstructed historical chart.
- `web/lib/chart.ts` labels an active problem plus an out-of-range trend
  `critical`. That heuristic cannot establish clinical urgency. Defaults in
  `reference.ts` also mix laboratory ranges with treatment goals.
- The doctor model implementation raises `NotImplementedError`; this needs
  implementation, not just a key. Requests, research and approvals that run
  the reminder agent cannot complete. The secretary model module is absent.
- The lab tab renders a fixed sample panel under the selected patient's name
  and uploads generated text. It is not yet a working photo/PDF workflow.
  `extract_analytes` returns an empty list. Speech returns no transcription
  or audio, and note embedding currently returns a zero vector.
- Coverage is visible in the patient banner, but a complete eligibility or
  scheduling workflow is not. Authentication remains an `X-Role` header.
- The database does not yet implement the proposed hypertables, continuous
  aggregates or vector retrieval. These are later infrastructure work, not
  prerequisites for improving the current frontend.

---

## 2. Design principles for the clinician

Everything below follows from a few facts about how clinicians work.

**The first ten seconds decide the visit.** Before a doctor says a word they
need: who this is (name, age, sex, photo), why they are here, what could kill
them (allergies, anticoagulation, code status, critical results), what changed
since last time, and what is due. If the UI makes them hunt for any of these it
has failed before the encounter starts.

**Reduce work within the visit.** Burnout has organizational, staffing and
administrative causes as well as interface causes; a redesign alone cannot
solve it. Judge each surface on whether it reduces searching, repeated entry
and unnecessary interruptions. AHRQ's [ambulatory workflow toolkit](https://digital.ahrq.gov/health-it-tools-and-resources/evaluation-resources/workflow-assessment-health-it-toolkit)
supports evaluating the clinical and administrative workflow around the
technology. Our product hypothesis is that reviewable drafts and a concise
chart overview can reduce effort; measure that rather than claiming it.

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

The allergies table and agent context are now implemented. Verification
provenance and medication safety checks remain follow-on work. Receiving an
allergy list in model context is not equivalent to checking a medication
against it.

### 3.2 Body tab

Today: a 3D model, specialty filter, date-mapped slider and findings list with
trend arrows. The slider does not yet reconstruct values and status as of a
past date; see section 11.3.

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
- Persist useful annotations with patient, region, author and time. Distances
  measured on this generic atlas describe the model, not the patient. Never
  save those distances as wound, lesion or circumference measurements.
  Patient measurements need an actual examination or a calibrated,
  patient-specific source; recording them is a separate workflow.
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

Today: visits, procedures, medication starts and notes use real dates grouped
by year. Encounter grouping, source filtering and medication stop/dose-change
history remain proposed.

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

Today: region details include trend charts, default reference bands,
medication starts, problems and related regions. The next work is making
sources, dates, missing data and individual targets explicit.

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

Today: pending and decided cards have before/after and a plain-text footer
joining source, confidence and citations. Bulk approval is hidden for chart
changes. The UI audit list is session-local; it is not a complete persisted
history of clinical decisions.

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
- Show evidence availability, conflicts and `validation_flags`. A model's
  self-reported confidence is not a calibrated probability of correctness;
  relabelling it "high" does not fix that. Keep it out of the primary review
  surface unless calibration has actually been evaluated.
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

Today: a fixed sample panel is rendered with the current patient's name and
uploaded as generated text. The extractor returns no analytes. Build a real
file-selection and verification flow before calling this photo extraction.

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

1. Allergy reconciliation and verification provenance (display already exists).
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
- Keyboard first: accessible tab navigation and a command palette for
  patients, views and actions. Avoid overriding browser tab shortcuts such as
  Ctrl/Cmd+W and Ctrl/Cmd+1..9. Scope canvas shortcuts to a focused canvas and
  disable them while typing in any editable field.
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

Design constraints for all of these: the number comes with its date, source
and units; laboratory ranges and individual goals are distinct. Use consistent
colour with text labels, but replace the current heuristic `critical`/`clear`
language as described in section 11.3. Provide a printable chart summary.

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
- Existing proposal rules reject web-tier evidence for chart changes and
  require baseline evidence for reminder changes. Medication allergy and
  interaction checks are still proposed; do not present them as implemented
  merely because allergies are in the model context.
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
- FDA clinical decision support: design for independent review of the basis
  of a recommendation. Citations or cautious wording alone do not establish
  regulatory status; assess the actual function and intended use against the
  [current FDA CDS guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software).
- Certification, interoperability and reimbursement requirements depend on
  the deployment and applicable program. A FHIR endpoint alone establishes
  neither certification nor readiness for a clinical deployment. This needs
  separate assessment after the hackathon scope is proven.
- Accessibility: use [WCAG 2.2](https://www.w3.org/TR/WCAG22/) AA as the design
  target, with a usable chart/list view when WebGL is unavailable.
- The 3D atlas licence (CPAL-1.0) and any data licence on its assets need a
  decision before a public or commercial release; this was deferred during the
  merge and remains open.

---

## 9. Prioritised roadmap

Build one convincing primary-care visit before adding another specialty or
workflow. Effort below is relative frontend effort, not a delivery estimate.

| Order | Deliverable | Value in the demo and in practice | Effort / dependency |
| --- | --- | --- | --- |
| P0 | Reliable local startup; clear loading, empty and unavailable states | The first screen works and explains a missing API without losing work | Small; running clinic API required for chart data |
| P0 | Correct identity, date/value semantics, urgency labels and sample-data labels | The viewer can trust what the screen claims | Small–medium; current chart payload supports most fixes |
| P0 | Fix atlas selection/label placement and retain a readable findings list | A click consistently reveals the right problem, even without 3D | Medium; frontend only |
| P0 | Visit overview and paired diabetes/kidney trends | Explain what changed in under a minute | Medium; derive dated facts from current chart, no new AI needed |
| P0 | One reviewable suggestion with evidence, explicit pending state and confirmed save | Demonstrate clinician control and a visible chart update | Medium; backend model and approval path are an explicit dependency |
| P1 | Medication review with dose, frequency, source and last-review status | Make the visit useful beyond the anatomy view | Medium; display can start now, persisted reconciliation needs API work |
| P1 | Patient explanation view and printable visit summary | Give the 3D view a second, understandable purpose | Medium; include approved facts only |
| P1 | Compact results/follow-up worklist | Show who owns the next step and whether it was completed | Medium–large; durable ownership/status needs backend support |
| Stretch | Real lab-file review, encounter-note editing, schedule/front-desk view | Extend the same visit story | Choose one only after P0 passes rehearsal |

Defer database scaling, a new mobile app, ambient recording, broad risk-score
calculators, autonomous treatment changes, billing and a full EHR replacement.
FHIR integration, real identity/access and deployment governance belong to a
post-hackathon pilot plan. Do not spend frontend time building screens whose
write operations the API cannot yet perform.

---

## 10. Decisions for the team

- Primary care is the chosen first setting. Keep Jane's longitudinal diabetes
  and kidney chart as the main story; the trauma prototype is a separate demo.
- Proposed navigation decision: the visit overview is the default landing
  surface, with Body, Trends and Chart as connected views. The anatomy is a
  strong visual index, but medication reconciliation and non-anatomic issues
  must remain easy to reach without manipulating a model.
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

---

## 11. Frontend experience: a useful visit that judges can understand

Added 2026-10-10. This section is a product recommendation based on the
integrated implementation, the team's frontend scope, and the sources linked
below. The proposed layouts, sequence and rehearsal targets are our design
judgments; they are not clinical practice guidelines or measured outcomes.

### 11.1 The promise and the audience

**Meridian helps a primary-care clinician understand what changed, review the
basis for a proposed action, and leave a clear next step.** Make that promise
visible before explaining agents, anatomy rendering or the database.

The clinician needs a compact overview and fast access to source records.
The rooming nurse or medical assistant needs a way to surface discrepancies
for review. The patient needs a comprehensible explanation and next steps.
The front desk needs scheduling and coverage context without clinical drafting
controls. Support one clinician visit well for the hackathon, and describe
these handoffs as the path to a useful team product.

Position a future pilot as a chart-review and visit-support workspace that
could integrate with an existing EHR. Replacing prescribing, orders, billing,
inbox routing and record exchange is a much larger undertaking. Our current
demo does not establish integration with a production EHR.

### 11.2 One connected screen, with a clear route through it

Use a compact **Visit overview** above or beside the body: reason for visit
when available, three dated changes, unresolved items, and medications and
allergies within one click. Do not generate a reason for visit from diagnoses
if no appointment or encounter supplies it. Label it "Not recorded."

Keep the body and a detail panel synchronized. Selecting a kidney marker or
the kidney row should select the same record, show the same date and open the
same trend. The list is the reliable navigation surface; the 3D view adds
spatial context. Keep research, assistant reasoning and secondary tools
collapsed until requested so they do not compete with the visit.

Three connected moments can provide the visual impact:

1. **See the change.** A dated A1c trend and kidney findings appear together
   while their associated regions highlight. Show related data, not an
   animation implying one condition caused another. NIDDK identifies eGFR
   and urine albumin as complementary markers used in kidney monitoring;
   that supports displaying both, rather than a lone creatinine number.
   [NIDDK: CKD tests and monitoring](https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/tests-diagnosis)
2. **Inspect the basis.** Click a result to reveal its value, unit, collection
   date and source. Open a related medication start on the same time axis.
   Say "started on this date" rather than claiming the medicine caused a
   later change. A fact-based comparison can be computed without an LLM.
3. **Make one accountable change.** Review a supported draft, inspect its
   field differences and evidence, then approve. Only a confirmed API save
   changes the chart. Briefly highlight the saved row and offer "View in
   chart"; approval itself must not turn a disease marker healthy.

For an accessible patient explanation, offer larger labels and plain-language
descriptions of approved chart facts, with a printable summary. Keep the
patient's chosen goals and concerns visible when actually recorded. Offer a
language preference and human-reviewed translations later; a decorative
language switch is not translation support.

### 11.3 Clinical meaning must survive the visual design

**Structured records and narratives both belong in an EMR.** USCDI includes
clinical notes and assessment/plan alongside problems, medications, allergies,
vital signs and laboratory results. Lead chart review with structured facts
and trajectories, while keeping narratives available for symptoms, examination,
reasoning and plans. A paragraph is not a substitute for a dated measurement
or an order. These sources define data and safety principles, not a required
screen layout or certification of this hackathon interface.
[ONC: USCDI data classes](https://healthit.gov/wp-content/uploads/2021/09/ONC-Provider-Webinar_508.pdf)

The implemented allergy summary remains visible for safety and opens a
structured list of substance, reaction, severity and recorded status. Recorded
dates do not imply clinician reconciliation. This follows the documentation
issues described in
[AHRQ: Improving allergy documentation](https://digital.ahrq.gov/ahrq-funded-projects/improving-allergy-documentation-and-clinical-decision-support-electronic-health).

| Display issue | Recommended behavior | Relevant frontend files |
| --- | --- | --- |
| Out-of-range becomes "Critical" | Use "Outside displayed range", "Changed" or "Needs review" with the reason. Reserve critical/urgent language for an explicit, sourced clinical flag. | `web/lib/chart.ts`, `reference.ts`, `data.ts` |
| No finding looks "Clear" | Distinguish "No recorded finding", "Not assessed" and a documented normal result. Missing data cannot establish health. | `chart.ts`, body and region tabs |
| Goal and reference range share a band | Label laboratory reference intervals, clinician-set goals and demo defaults separately. Unknown units or missing ranges must be visible. Avoid deriving diagnoses from chart colours. | `reference.ts`, `trend-chart.tsx`, `region-tab.tsx` |
| "Chart as of" exposes later data | Initially call this "Findings recorded by" and explicitly label current-value panels. A true historical mode must filter every observation, note and medication and needs historical status data the API does not yet provide. | `body-tab.tsx`, `chart.ts`, `data.ts` |
| "Since last visit" lacks a baseline | Name the comparison encounter/date and use only observations available on each side. If there is no suitable baseline, say so; two arbitrary points are not a last-visit comparison. | `chart.ts`, overview and trend components |
| Anatomical precision exceeds source data | Describe the model as an illustrative map. A generic kidney chart item cannot establish left-sided disease merely because it maps to `kidney_l`. Keep laterality "unspecified" unless the source records it. | `atlas.ts`, scene labels, region tab |
| Binary fallback fabricates demographics | Preserve the API's recorded sex value and support unknown values. Do not map every non-male record to female or infer screening eligibility from the mesh. | `chart.ts`, `types.ts`, patient banner |
| Medication list implies actual use | Separate prescribed/recorded status from patient-reported use and verification. "Reviewed, no changes" should be possible once persistence exists. | medication view and patient banner |

Medication reconciliation is a comparison of available information and actual
use, not just a list. AHRQ describes the value of side-by-side lists,
chronological dosage information and recording reconciliation even when
nothing changes. Start with those concepts before attempting a homemade
interaction engine. [AHRQ: Medication reconciliation](https://digital.ahrq.gov/medication-reconciliation)

For the demo, preserve the dated seed records and show an explicit scenario
date if a fixed visit is needed. Never silently move clinical dates to make
old data look fresh. A1c goals, kidney staging and screening eligibility are
contextual; the frontend should display documented assessments and sources,
not invent a universal treatment or screening rule.

### 11.4 Review, identity and follow-up are the practical differentiators

Keep patient name plus DOB or full record identifier on the active chart and
on every consequential review card. The generated six-character `R-` display
identifier is a demo convenience, not a validated MRN. A draft stays bound to
the patient for whom it was created when the user switches tabs. Show that
patient's identity at approval and never silently retarget the request.
These choices respond to the identification concerns addressed in the
[2025 SAFER patient identification guide](https://healthit.gov/resources/2025-safer-guide-patient-identification/).

An approval card should contain the proposed action, changed fields, source
facts and their dates, applicable evidence, unresolved issues and a clear
status. Prefer "Source available" or "Missing evidence" to a confidence
percentage. Preserve `locator`, `validation_flags`, target identifiers and
structured before/after data through `api.ts` and `chart.ts`; the current
display mapping loses useful detail. Evidence links should open the actual
passage or source record, not search for a title.

Use the states **Draft → Saving → Saved** with a separate **Failed** state.
Disable duplicate submissions, preserve edits on error and distinguish a
failed save from a successful save whose chart refresh failed. Reconcile with
the server before retrying an ambiguous mutation. An edit-and-approve UI can
use the API's existing `edits` support once the model-dependent approval path
works. A durable undo or task-assignment feature requires an agreed backend
contract; a local animation cannot stand in for either.

For results and care gaps, separate **reviewed**, **patient contacted**,
**scheduled** and **completed**. A delivered WhatsApp reminder does not mean a
test happened. The proposed worklist should show an owner, next action and
due date; until persisted ownership exists, describe it as a preview rather
than pretending work has been assigned. This follows the emphasis on closing
the results loop in the [2025 SAFER results and follow-up guide](https://healthit.gov/resources/2025-safer-guide-test-results-reporting-and-follow-up/).

Distinguish screening from monitoring an established condition. A USPSTF
screening source does not automatically support disease-management follow-up.
Validate each demo reminder's source and applicability. When history is
incomplete, show "History needed" instead of declaring the patient overdue.
Later, accommodate completed elsewhere, declined, deferred with reason and
not applicable; do not collapse these into a generic done flag.

### 11.5 A three-minute demonstration

| Time | Presenter action | What the viewer learns |
| --- | --- | --- |
| 0:00–0:25 | Open Jane's explicitly synthetic visit; identify her, the recorded visit context and allergies | This is a clinician's workspace with recognizable priorities |
| 0:25–1:05 | Open the dated diabetes and kidney trends from the overview/body | The body helps connect a longitudinal chart; the values remain inspectable |
| 1:05–1:40 | Ask for a concise summary or review a pre-seeded pending note suggestion | The assistant exposes the chart facts behind its draft |
| 1:40–2:20 | Review the diff, edit if supported, approve once and show the persisted chart change | Human judgment controls the write; the interface confirms what actually happened |
| 2:20–3:00 | Show the next follow-up and a patient-readable explanation | The visit ends with understandable next steps |

Choose a note or supported update to an existing row for the first complete
write demonstration. Audit new-row creation before choosing extracted labs:
`services/approval.py` currently skips non-note writes when `target_id` is
absent. Together with the unfinished model, that is a backend dependency to
resolve, not something the frontend should conceal.

If the live model is unavailable, a pre-seeded pending suggestion may still
support a rehearsal, but the actual approval endpoint must work. Any scripted
preview must be explicitly selected and labelled synthetic/scripted; never
substitute it automatically for a failed live request. A read-only chart demo
is a valid fallback with an honest explanation of the unfinished write path.

### 11.6 Frontend acceptance criteria and rehearsal

These are proposed targets to test on this machine, not performance claims:

- A new viewer can identify the patient and name two dated changes within
  30 seconds; opening the evidence for either change takes at most two clicks.
- Clicking each marker and its matching list row reveals the same condition,
  value and date. Heart and kidney labels remain distinct at presentation
  size; selecting a row never moves a label onto a different organ.
- A user can review one suggestion without hiding the supporting chart.
  Pending work never appears as an approved clinical fact. Reloading verifies
  that a claimed successful save persisted.
- Switching patients during an outstanding request leaves its result and
  draft attached to the original patient. An unavailable API or failed save
  produces a useful retry path without discarding the current draft.
- The core visit works by keyboard, at 200% zoom and without WebGL. Provide
  visible focus, readable text/contrast, text alongside colour, usable target
  sizes and reduced-motion behavior. Use the [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
  criteria as the reference; do not claim conformance from a quick demo check.
- Check a 1366×768 laptop and the actual projector. Chart text remains legible
  with the assistant open. Loading the atlas does not block access to the
  findings list; WebGL failure offers that list immediately.
- Rehearse once from a cold start and once with the backend disconnected.
  Keep fonts and anatomy assets available locally where practical. Record
  observed load times and the exact demo/backend configuration.
- Ask a clinician or clinical trainee to narrate a short task using synthetic
  data: find the last relevant result, verify medications, review a draft and
  identify follow-up. Record hesitations and errors, not just aesthetic
  feedback. Judge success by task completion and fewer context switches;
  make no claim of reduced burnout or better outcomes without evidence.

### 11.7 Scope boundaries for this frontend effort

**Can build against current reads:** visit overview, dated comparisons,
connected body/list navigation, medication display, evidence presentation,
clear empty/error states and an approved-facts explanation view.

**Coordinate before promising writes:** working model-backed approvals,
new observation insertion, persisted medication reconciliation, encounter
signing, results acknowledgement, assigned follow-up and document extraction.
Track each dependency explicitly and agree the minimum payload before UI work.

**Keep in the later backlog:** ambient recording, universal drug-interaction
checks, autonomous medication adjustments, broad risk prediction, billing,
full FHIR integration and production deployment. The hackathon's strongest
claim is a clear, verifiable visit workflow demonstrated with synthetic data.

## 12. Manual chart work: implementation and next priorities

Implemented locally on October 10, 2026. The chart now supports a practical
capture workflow without depending on the unfinished AI model:

- **Record vitals** from Overview or Vitals & trends. Capture measured date/time,
  paired BP, weight in kg and pulse. Optional values remain absent rather than
  becoming zero. Saves persist to observations and refresh the dated trends.
- **Maintain structured lists:** add problems, add/edit recorded medications,
  and add/edit allergy records. Medication capture documents history; it does
  not issue a prescription. The clinician explicitly chooses a chart region
  instead of accepting an invented anatomical association.
- **Record patient review:** medication reconciliation records reported use
  separately from chart status; allergy review requires explicit confirmation.
  Review time and optional notes persist. A changed list marks the prior review
  stale, and saving a review against outdated records is rejected.
- **Document negative allergy history explicitly:** a no-known-drug-allergy
  assertion requires patient/caregiver confirmation. Active drug allergies and
  active NKDA cannot be added together through these manual workflows. Resolving
  an NKDA assertion preserves it as inactive history.
- **Visit draft:** reason, assessment and plan persist per patient as an
  unsigned draft. Prior saves remain in the audit log; the UI shows the latest
  draft. Saving does not sign an encounter or place orders.
- **Actionable follow-up:** update existing task due dates and statuses, including
  Done and Paused. Routine chart work no longer exposes simulated SMS buttons.

Forms identify the patient by name, DOB and record ID. Unsaved values survive
tab switches in memory; only explicitly saved entries survive a browser reload.
Writes use submission IDs to prevent duplicate retry saves, check record
ownership, and preserve edit history in the same transaction. If a save succeeds
but chart refresh fails, retry refresh rather than create another entry.

This remains a local hackathon workflow. Clinician authentication and roles,
formal encounter lifecycle/signing, terminology-backed prescribing, multiple
visit drafts, accessible revision history, result acknowledgement, document
ingestion and assigned follow-up remain separate requirements. Manual action
logs do not establish authenticated clinician identity. The current inline text
storage also limits an individual entry's size; longer note storage needs a
schema change before production use.

For the next frontend pass, prioritize timeline filtering and source documents,
then a single encounter workspace bringing capture, draft review and follow-up
together. Add results acknowledgement and assigned owners only once the backend
can persist their actual status. Keep unsupported AI paths clearly described
until they can be demonstrated end to end.

### Patient navigation and information density

The chart's plus button now opens a centered patient search rather than a menu
of chart views. Search queries the patient directory by name, DOB or record ID,
returns at most 20 matches with a refinement prompt, and loads the selected
chart on demand. DOB and record ID distinguish results; recently opened charts
provide shortcuts. Patient-name navigation uses the same search, while a More
menu holds secondary chart views. The plus button stays visible as tabs grow.

Overview and problem views now lead with dated measurement rows. Expanding a
row shows a compact trend, selectable source details and an exact-values table.
Systolic and diastolic readings share one BP row and plot only when their latest
collection timestamps and units match. The dedicated Vitals & trends view
retains the full measurement collection and date filtering. Problem views no
longer repeat measurements as both graphs and latest-result lists, reproduce
generated summaries of those values, or repeat global family history. Related
notes remain available on expansion. New chart tabs start at the top.

## 13. Backend-aligned clinical workspace and diagnostic data (2026-10-10)

### Clinical direction

Keep Meridian's white chart surfaces, deep teal assistant, restrained jade
controls, and generous space. Use amber with an explicit label for due tasks
and proposals awaiting review. Use red for recorded severe allergy reactions;
do not manufacture critical lab flags from generic numeric thresholds.

The useful principle in the team's proposed architecture is separation of the
longitudinal record, today's encounter draft, and unapproved proposals. Claims
that all legacy EMRs are merely billing systems, or that clinical records should
be mostly quantitative, are too broad to guide this product. Clinical care needs
both discrete observations and narrative reasoning. Symptoms, imaging impressions,
pathology interpretation, and assessment/plan require meaningful text. The goal
is to avoid repeatedly entering the same facts, not to eliminate narrative.

For diagnostics, keep individual measurements separate from the report that
provides their context and interpretation. HL7 distinguishes Observation from
DiagnosticReport, which can connect discrete results, images, and narrative
interpretation. This is a design reference, not a claim that Meridian currently
implements FHIR interoperability. Sources: [Observation](https://hl7.org/fhir/observation.html),
[DiagnosticReport](https://hl7.org/fhir/diagnosticreport.html), and the
[diagnostics module](https://hl7.org/fhir/diagnostics-module.html).

### Current contract: available does not mean complete

| Backend capability | Frontend treatment | Current boundary |
| --- | --- | --- |
| Patient search and full chart | Centered search; persistent identity and allergies; longitudinal overview | Record label is derived from the UUID, not a hospital-issued MRN. No code-status or advance-directive fields. |
| Conditions | Active/history list and direct add form; anatomy detail; reviewed AI updates | Direct problem editing/resolution has no endpoint. AI updates are available through pending proposals. No ICD/SNOMED coding contract. |
| Medications | Add, edit, stop via recorded status; history; reconciliation | Medication records are not prescriptions, e-prescribing, pharmacy transmission, or an inpatient MAR. |
| Allergies | Substance, reaction, severity, active/history, direct editing and reconciliation | An explicit NKDA assertion is different from a missing allergy history. |
| Observations and vital entry | Compact BP, weight, pulse and other recorded trends; exact-values flowsheet | Direct entry currently accepts paired BP, pulse, and weight. Other observations can be read if present. No continuous wearable feed. |
| Encounter summaries and notes | Recent activity, timeline, recorded procedures | No separate surgical-history registry; no linked encounter diagnosis or completed SOAP/signature workflow. |
| Visit draft | Open editor for visit date, reason/history, assessment, and plan | One unsigned draft per patient in entry state. No physical-exam field, encounter finalization, order cart, or signing endpoint. |
| Proposed changes | Before/after review, individual approval, selected reviewed batch approval, rejection | Approval inserts new records and applies existing-record updates after field, patient ownership and stale-value checks. Notes receive real Gemini embeddings. Approval is not a legal visit signature. Provider failures roll back the request. |
| Typed and audio doctor requests | One command surface; recording, playback/discard, transcription, draft review and spoken responses | Live Gemini classification/drafting, ElevenLabs Scribe transcription and voice synthesis are connected. Configuration comes from the backend; permission and provider failures remain explicit. |
| Documents | S3 upload; Gemini extraction; dated numeric proposals; approved results and provenance in chart trends | Numeric extraction supports PDF, image, TXT and CSV reports. Missing/ambiguous collection dates are not invented. No report-list/download endpoint; S3 read/delete probes remain denied. |
| Reminders and appointments | Dated follow-up, status edits, all recorded appointments in history | Scheduling mutations and secretary chat require the secretary role. Do not expose those as unrestricted doctor actions. Reminder job runs across the clinic, not just the viewed patient. |
| Coverage and eligibility | Separate history/coverage view; optional planned-service review with payer evidence | Uses stored coverage and model/payer documents. Not a live insurer eligibility transaction, claim submission, or guaranteed authorization determination. |
| Research and screening evidence | Cited results in assistant and research view; reviewed screening proposals | Live Snowflake USPSTF/PubMed retrieval, medical web grounding, Gemini answers and claim verification are connected. Returned citations are grounded in retrieved passages. Clinical applicability still requires clinician review. |

### Refactor implemented in this working tree

- Overview distinguishes the longitudinal record from an explicit visit entry
  point. The next appointment aligns right. Recent chart activity has a short
  chronological digest; the full timeline remains available.
- Allergies include recorded reactions and severity in the fixed safety banner,
  including assistant full-screen view. Missing safety fields are not invented.
- Diagnostics is a primary chart section rather than a synthetic lab document.
  Search recorded tests, inspect latest values, expand trends, and inspect the
  full dated result history with source and document identifier.
- Vitals no longer repeats the diagnostic-results module. Pulse is graphed when
  present; period-average BP uses matching recorded timestamps and sources,
  reports sample count, and is labeled an arithmetic mean. It is not mean
  arterial pressure, a treatment target, or a diagnostic conclusion.
- Visit context remains available beside documentation through an expandable
  snapshot. Old vitals keep their dates and are never relabeled today's vitals.
  Save is explicitly an unsigned draft, with no claim to submit orders.
- Real microphone capture replaces the sample transcript. Process dictation sends
  recorded audio to the live speech adapter; the transcript and proposed changes
  are returned for review. Unsupported recording, denied microphone access,
  provider failures, upload failure and empty extraction remain explicit states.
- Nonfunctional manual routing/re-routing controls are removed. The backend owns
  request classification. Chart changes require explicit approval; batch approval
  includes only proposals the clinician marked reviewed for the same patient.

### Clinical and diagnostic findings: recommended data depth

This is the highest-value next data expansion. Build a report-centered workflow
without losing the exact result-level data clinicians need. The proposed fields
below are a product specification, not fields that already exist in the API.

**Common report context.** Preserve patient, report identifier/accession,
report type, originating organization, ordering clinician, relevant encounter,
collection/performed time, received time, finalization time, preliminary/final/
corrected status, original attachment, and report author. A result collection
is not automatically a named CBC or metabolic panel. Group it as a panel only
when the incoming source supplies that relationship.

**Laboratory values.** Store a stable test code where available, displayed test
name, numeric/textual/coded result type, units, original reference interval,
source-issued abnormal and critical flags, specimen type/site, collection time,
method, and observation identifier. Keep reference intervals as source data;
they can vary by method and patient context. An absent range means unavailable,
not normal. A raw number without units is not suitable for a cross-source trend.

**Panels and interpretation.** Offer compact rows for a panel, an expanded
result table, and a small trend only when there is meaningful history. Compare
compatible tests and units across time. Expose the original report beside
extracted values. Separate the source's interpretation from AI explanation and
from the clinician's assessment. Do not generate a panel of normal values to
make a sparse demo appear complete.

**Radiology and imaging.** Prioritize indication, modality, body site/laterality,
performed time, comparison studies, findings, impression, and recommendations.
The impression should be easy to scan, with the full report expandable. A
PACS/DICOM viewer link needs an actual study identifier and integration; an
anatomy pin is not a substitute for an image or a radiology diagnosis.

**Pathology.** Keep specimen/site/laterality, procedure/collection date,
preliminary versus final diagnosis, narrative microscopy, structured fields
when the source provides them, addenda, and the signing pathologist. Do not
infer staging or malignancy from an isolated phrase. Highlight source-provided
amendments so the clinician can distinguish the current interpretation from
an earlier report.

**Microbiology.** Keep specimen and collection time, preliminary/final status,
organism identification, reported susceptibility with method and interpretive
category, and the lab's comments. Preserve corrections. Do not derive a
susceptibility recommendation from an organism name alone.

**Clinical findings and transcription.** Symptoms, relevant negatives,
physical findings, and assessment are valuable narrative and structured data.
Voice transcription should be attributed to its source and encounter, reviewable,
and editable before it becomes a signed clinical note. AI-extracted diagnoses,
medication changes, and result values remain proposals until confirmation.

**Review and follow-through.** A diagnostic result should eventually have an
acknowledgment state, reviewing clinician/time, related follow-up task, and
patient communication status. Reviewing a report, completing a follow-up task,
sending a reminder, and documenting a patient conversation are separate events.
Do not equate an SMS send with result review or care completion.

### Additional domains: integrate deliberately

| Domain | Next useful clinical surface | Needed backend support |
| --- | --- | --- |
| EHR history | Longitudinal medications/problems, family and surgical history, immunizations, encounter-linked notes | Persistent surgical history and immunization resources; encounter relationships and coding. Billing/claims stay separate from the primary clinical canvas. |
| Vitals and wearables | Timestamped vitals plus clearly attributed home/device observations | Device identity, acquisition method, measurement quality, cadence, units, and reconciliation. Do not label sporadic office readings real-time. |
| Genomics | A reviewed report, indication, laboratory interpretation, and source-linked actionable findings | Report/version metadata, variant identifiers and method, interpretation, consent/access policy, and clinical review. No automatic treatment changes from unreviewed variants. |
| Public health and demographics | Relevant regional guidance linked to the patient's context | Source, geographic scope, publication/update dates and applicability. Population data must remain distinct from a patient's measured history. |
| Medical literature and guidelines | A question-specific answer with citations and publication/version context | Live doctor adapter and evidence retrieval are connected. Publication/version metadata and deeper patient-specific applicability review need further expansion; chart/plan actions require approval. |

### Recommended build order

1. The doctor model adapter, speech adapter and numeric lab extraction are now
   connected and verified with real providers through HTTP requests and committed
   synthetic records in an isolated database. Typed and voice drafting, approval,
   real note embeddings, clinical answers, screening review, secretary payer
   lookup, S3 upload and approved lab chart refresh passed. Continue to keep
   provider credential checks distinct from complete workflow checks. The frontend
   proxy now allows up to five minutes for these multi-call workflows instead of
   cutting them off at 30 seconds; improve response speed as a follow-up.
2. Add document metadata listing and authenticated original-report viewing.
   Resolve object read/cleanup permissions without exposing storage credentials
   to the frontend. Preserve document provenance on approved observations.
3. Expand diagnostics with report/result separation, source flags/reference
   intervals, and review acknowledgment. Keep reported units and collection dates
   intact. Fix chart-series grouping to distinguish analyte, unit, and context
   before importing heterogeneous sources.
4. Add encounter identity, structured exam/context, explicit finalization and
   audited amendments. Draft save, chart mutation approval, signing, and order
   transmission need separate states and endpoints.
5. Add a practical reviewed order workflow and then source-specific integrations
   for imaging, immunizations, wearables, genomics, or claims when the team has
   a concrete user story. Prioritize one complete clinical workflow for the demo
   over placeholder tabs for every possible medical data source.

The ongoing cloud regression run was stopped at the user's request. The test
schema isolation fix remains in the working tree. No full backend regression
pass or new push is claimed for this refactor.
