# AI-Powered EMR: Full System Graph

Everything from `system-design-draft-1.md` in one flowchart.

How to read it:

- **Yellow dashed box** = a runtime decision. The box's name matches the subgraph next to it that holds the decision itself.
- **Red dashed box** = an open design decision we haven't made yet.
- **Solid arrow** = control flow. **Dotted arrow** = a read or write to a data store.
- Endpoint and table names are proposals.

```mermaid
flowchart TB
  classDef decision fill:#fff3bf,stroke:#f08c00,stroke-width:2px,stroke-dasharray:5 3,color:#000
  classDef open fill:#ffe3e3,stroke:#e03131,stroke-width:2px,stroke-dasharray:5 3,color:#000
  classDef actor fill:#e5dbff,stroke:#7048e8,color:#000

  EMR(["AI-Powered EMR<br/>Hack Knight Fall 2026"]):::actor
  Doc(["Doctor"]):::actor
  Pt(["Patient"]):::actor
  Nightly(["Nightly job - APScheduler"]):::actor
  D1box["D1: Deployment target"]:::decision

  %% ================= D1: Deployment target =================
  subgraph D1 ["D1: Deployment target"]
    D1q{"Hackathon POC or production?"}
  end

  %% ================= Hackathon stack =================
  subgraph Hack ["Hackathon stack - no sign-in, synthetic data only"]
    HWeb["Web dashboard<br/>React, Tailwind, shadcn/ui<br/>React Three Fiber + drei, GLB human mesh"]
    HMobile["Expo app<br/>mic with Dictate/Ask toggle, photos, reminders"]
    HTypes["TypeScript client generated from FastAPI OpenAPI"]
    HAPI["FastAPI + Pydantic v2<br/>google-genai agents, APScheduler"]
    HDB["SQLAlchemy/SQLModel async, asyncpg,<br/>Alembic, pgvector package"]
    HExt["Gemini API, Snowflake Cortex,<br/>ElevenLabs, Twilio, Stedi"]
    HHost["Web on Vercel"]
    D2box["D2: Open stack choices"]:::decision
    subgraph D2 ["D2: Open stack choices"]
      D2a{"Web framework?"}
      D2a --> D2a1["Next.js"]
      D2a --> D2a2["Vite + React"]
      D2b{"DB layer?"}
      D2b --> D2b1["SQLAlchemy 2 async"]
      D2b --> D2b2["SQLModel"]
      D2c{"Agent style?"}
      D2c --> D2c1["Plain function calling"]
      D2c --> D2c2["Google ADK"]
      D2d{"Snowflake client?"}
      D2d --> D2d1["Cortex REST via httpx"]
      D2d --> D2d2["snowflake-connector-python"]
      D2e{"API host?"}
      D2e --> D2e1["Railway / Render / Fly"]
      D2e --> D2e2["Laptop + Cloudflare Tunnel"]
      D2f{"Types generator?"}
      D2f --> D2f1["openapi-typescript"]
      D2f --> D2f2["@hey-api/openapi-ts"]
    end
    HWeb --> HTypes
    HMobile --> HTypes
    HTypes --> HAPI
    HAPI --> HDB
    HAPI --> HExt
    HWeb --> HHost
    HAPI --> D2box
    D2box --> D2
  end

  %% ================= 0. One-time setup =================
  subgraph Setup ["0. One-time data setup"]
    Map["body_region_map + specialty_focus lookups"]
    Rules["reminder_rules baseline<br/>age-based screenings"]
    PDFs["USPSTF guidelines, PubMed abstracts,<br/>payer policy PDFs"] --> Stage["Snowflake stage"]
    Stage --> Parse["AI_PARSE_DOCUMENT"]
    Parse --> Chunk["SPLIT_TEXT_RECURSIVE_CHARACTER"]
  end

  %% ================= Data stores =================
  subgraph Tiger ["Tiger Cloud - time series + vectors in one Postgres"]
    TReg[("Regular tables<br/>patients, conditions, family_history,<br/>medications, documents, body_region_map,<br/>specialty_focus, reminder_rules, eligibility_checks")]
    THyper[("Hypertables<br/>observations, encounters")]
    TAgg[("Continuous aggregates<br/>vitals + lab trends")]
    TNotes[("notes + pgvector embeddings")]
    TSugg[("ai_suggestions")]
    TAudit[("audit_log")]
    TSched[("reminder_schedule")]
    TSms[("sms_messages")]
    THyper --> TAgg
  end

  subgraph Snow ["Snowflake - evidence engine"]
    SChunks[("guideline_chunks")] --> SCSS["Cortex Search service<br/>Cortex Guard on"]
  end

  Files[("File storage<br/>original images")]

  %% ================= Voice entry + D4 =================
  subgraph Voice ["Mic"]
    Mic["Mic button + Dictate/Ask toggle<br/>starts in Dictate, remembers last mode"]
    D4box["D4: Toggle mode"]:::decision
    subgraph D4 ["D4: Toggle mode"]
      D4q{"Which mode is the toggle on?"}
    end
    Mic --> D4box
    D4box --> D4
  end

  %% ================= 1. 3D body view =================
  subgraph F1 ["1. 3D body view + specialty overlay + timeline"]
    F1in["GET /patients/id/body-state?specialty=..."]
    F1q["Conditions joined to body_region_map,<br/>filtered by specialty_focus,<br/>timeline events, trend series"]
    F1render["Map regions to mesh names, color + pulse overlays,<br/>emphasize specialty, dim the rest"]
    F1slider["Timeline slider filters events in the browser"]
    F1click["Click region - GET /patients/id/regions/heart<br/>conditions, meds, observations detail panel"]
    F1in --> F1q
    F1q --> F1render
    F1render --> F1slider
    F1render --> F1click
    F1render -->|"switch specialty: re-query"| F1in
  end

  %% ================= 2a. Dictate =================
  subgraph F2a ["2a. Dictate - changes to the record"]
    F2in["POST /dictations<br/>audio + patient_id"]
    F2stt["ElevenLabs Scribe STT"]
    F2ctx["get_patient_context - read-only<br/>conditions, meds, recent vitals, reminders"]
    F2gem["Gemini: transcript + context + Pydantic schema<br/>field updates, schedule changes, SOAP note"]
    F2val["Validate schema, field allowlist, units + ranges"]
    F2ins["Insert ai_suggestions grouped by dictation_id"]
    F2tts["ElevenLabs TTS read-back<br/>I will mark hypertension controlled..."]
    D5box["D5: Send as Ask instead?"]:::decision
    subgraph D5 ["D5: Send as Ask instead?"]
      D5q{"Doctor taps Send as Ask instead?"}
      D5discard["Discard this dictation's<br/>pending suggestions"]
      D5q -->|"yes"| D5discard
    end
    F2in --> F2stt
    F2stt --> F2ctx
    F2ctx --> F2gem
    F2gem --> F2val
    F2val --> F2ins
    F2ins --> F2tts
    F2tts --> D5box
    D5box --> D5
  end

  %% ================= 2b. Ask =================
  subgraph F2b ["2b. Ask - questions + agent requests, never writes directly"]
    F2bin["POST /asks<br/>audio + patient_id"]
    F2bstt["ElevenLabs Scribe STT"]
    F2bcls["Gemini: classify request,<br/>clean up the question"]
    F2back["Ack to app:<br/>Looking into statin eligibility for Jane"]
    D6box["D6: Send as Dictation instead?"]:::decision
    subgraph D6 ["D6: Send as Dictation instead?"]
      D6q{"Doctor taps Send as Dictation instead?"}
    end
    D7box["D7: Ask request type"]:::decision
    subgraph D7 ["D7: Ask request type"]
      D7q{"Research question or screening review?"}
    end
    F2bin --> F2bstt
    F2bstt --> F2bcls
    F2bcls --> F2back
    F2back --> D6box
    D6box --> D6
    D7box --> D7
  end

  %% ================= 3. Approval =================
  subgraph F3 ["3. Approval queue - the only path that writes to the chart"]
    Q["GET /suggestions?status=pending<br/>cards: before/after diff, source,<br/>confidence, validation flags, citations"]
    Guard["Guardrails: Pydantic schemas, field allowlist,<br/>narrow tools, citations required, synthetic data"]
    D12box["D12: Doctor review"]:::decision
    subgraph D12 ["D12: Doctor review"]
      D12q{"Approve, edit then approve, or reject?"}
      D12all["Approve all per dictation,<br/>per-card toggle to leave one out"]
      D12q -.- D12all
    end
    F3tx["One transaction: write chart tables,<br/>mark approved, insert audit_log"]
    F3rej["Mark rejected with reason, insert audit_log<br/>chart unchanged"]
    F3refresh["Updated chart, body view refreshes"]
    D13box["D13: Post-approval side effects"]:::decision
    subgraph D13 ["D13: Post-approval side effects"]
      D13note{"Approved item is a note?"}
      D13rem{"Approved item is a reminder change?"}
      D13scr{"Affects screenings?<br/>family history, new condition, procedure done"}
    end
    F3embed["Gemini embed note text"]
    Guard -.- Q
    Q --> D12box
    D12box --> D12
    F3tx --> F3refresh
    F3tx --> D13box
    D13box --> D13
    D13note -->|"yes"| F3embed
  end

  %% ================= 4. Image processing =================
  subgraph F4 ["4. AI image processing"]
    F4in["Photograph paper lab report<br/>POST /documents"]
    F4save["Save original image"]
    F4gem["Gemini vision + LabReport schema<br/>test names, values, units, dates, confidence"]
    F4val["Validate units, flag low-confidence<br/>and out-of-range values"]
    F4ins["Insert documents row + ai_suggestions<br/>for new observations"]
    F4in --> F4save
    F4save --> F4gem
    F4gem --> F4val
    F4val --> F4ins
  end

  %% ================= 5. Research assistant =================
  subgraph F5 ["5. Research assistant - read-only"]
    F5in["Web chat"]
    F5agent["Gemini agent: question + tool list"]
    F5notes["search_patient_notes<br/>embed query, pgvector over notes<br/>+ lipid results from observations"]
    D8box["D8: Ask sees pending dictation? - OPEN"]:::open
    subgraph D8 ["D8: Ask sees pending dictation? - OPEN"]
      D8q{"Include this visit's pending suggestions?"}
      D8a["Option A - recommended<br/>include them, labeled unconfirmed"]
      D8b["Option B<br/>approved chart data only"]
      D8q -->|"A"| D8a
      D8q -->|"B"| D8b
    end
    F5guide["search_guidelines<br/>de-identified clinical query"]
    F5ans["Gemini: answer citing notes + guidelines"]
    F5cite["Check every claim has a cited source"]
    F5out["Streamed answer with citation chips"]
    D9box["D9: Came from Ask mode?"]:::decision
    subgraph D9 ["D9: Came from Ask mode?"]
      D9q{"Request came from Ask mode?"}
      D9tts["ElevenLabs TTS short summary on phone"]
      D9q -->|"yes"| D9tts
    end
    D10box["D10: Add to plan?"]:::decision
    subgraph D10 ["D10: Add to plan?"]
      D10q{"Doctor clicks add to plan?"}
      D10no["Nothing changes"]
      D10q -->|"no"| D10no
    end
    F5in --> F5agent
    F5agent --> F5notes
    F5notes --> D8box
    D8box --> D8
    D8a --> F5guide
    D8b --> F5guide
    F5guide --> F5ans
    F5ans --> F5cite
    F5cite --> F5out
    F5out --> D9box
    D9box --> D9
    D9tts --> D10box
    D9q -->|"no"| D10box
    D10box --> D10
  end

  %% ================= 6. Reminder agent =================
  subgraph F6 ["6. Reminder suggestion agent"]
    F6trig["Review reminders for patient<br/>triggers: approval, nightly job, Ask screening review"]
    F6base["Load reminder_rules baseline<br/>+ current reminder_schedule"]
    F6ctx["get_patient_context<br/>age, family_history, conditions, past procedures"]
    F6guide["search_guidelines<br/>first-degree relative diagnosed at 50"]
    D11box["D11: Reminder change needed?"]:::decision
    subgraph D11 ["D11: Reminder change needed?"]
      D11q{"Schedule already fits guidelines + risk?"}
    end
    F6prop["propose_reminder_change<br/>colonoscopy 45 to 40, reason + citation"]
    F6val["Validate against allowlist, require citation"]
    F6ok["Screenings up to date<br/>spoken too if from Ask"]
    F6trig --> F6base
    F6base --> F6ctx
    F6ctx --> F6guide
    F6guide --> D11box
    D11box --> D11
    D11q -->|"change needed"| F6prop
    D11q -->|"already correct"| F6ok
    F6prop --> F6val
  end

  %% ================= 7. SMS =================
  subgraph F7 ["7. SMS reminders"]
    F7edit["PUT /patients/id/reminders/r1<br/>change due date or pause"]
    F7sched["APScheduler job or POST /demo/run-reminders<br/>real or simulated date"]
    F7due["Query reminders due on or before today"]
    D14box["D14: Due and opted in?"]:::decision
    subgraph D14 ["D14: Due and opted in?"]
      D14q{"Scheduled, due, and patient opted in?"}
      D14wait["Wait for next run"]
      D14q -->|"no"| D14wait
    end
    F7render["Render message with no health details"]
    F7send["Twilio send SMS<br/>store SID, insert sms_messages, mark sent"]
    F7hook["Status webhook - delivered or failed"]
    D15box["D15: Patient replies STOP?"]:::decision
    subgraph D15 ["D15: Patient replies STOP?"]
      D15q{"Inbound reply is STOP?"}
      D15out["Set sms_opt_in to false"]
      D15q -->|"yes"| D15out
    end
    F7sched --> F7due
    F7due --> D14box
    D14box --> D14
    D14q -->|"yes"| F7render
    F7render --> F7send
    F7send --> F7hook
    D15box --> D15
  end

  %% ================= 8. Insurance (stretch) =================
  subgraph F8 ["8. Stretch: insurance eligibility + prior auth"]
    F8in["POST /patients/id/eligibility"]
    F8cov["Look up coverage: payer + member ID"]
    F8stedi["Stedi test mode vs mock payer<br/>active status, deductible, copay, benefits"]
    F8store["Insert eligibility_checks"]
    D16box["D16: Prior-auth question?"]:::decision
    subgraph D16 ["D16: Prior-auth question?"]
      D16q{"Does this order raise a prior-auth question?"}
      D16snow["Cortex Search over payer policy PDFs<br/>policy passage + citation"]
      D16q -->|"yes"| D16snow
    end
    F8sum["Gemini: coverage in plain English"]
    F8card["Coverage card + prior-auth note with citation"]
    F8in --> F8cov
    F8cov --> F8stedi
    F8stedi --> F8store
    F8store --> D16box
    D16box --> D16
    D16snow --> F8sum
    D16q -->|"no"| F8sum
    F8sum --> F8card
  end

  %% ================= Production =================
  subgraph Prod ["Production - many users, HIPAA-grade"]
    PBAA["Every vendor touching patient data signs a BAA<br/>Gemini on Vertex AI, Snowflake Business Critical,<br/>ElevenLabs enterprise or AWS HealthScribe"]
    PUsers["Clinicians: web + MDM-managed mobile"]
    PEdge["CloudFront + AWS WAF"]
    PAPIGW["API Gateway"]
    PIdP["Cognito + hospital SSO<br/>RBAC + care-team ABAC, break-glass"]
    PSvc["FastAPI on ECS Fargate<br/>private subnets, VPC endpoints"]
    PTiger[("Tiger Cloud via VPC peering<br/>row-level security, KMS per tenant")]
    PHL[("AWS HealthLake<br/>FHIR system of record")]
    PS3[("S3 SSE-KMS + Object Lock<br/>audio, images, documents")]
    PEHR["Hospital EHRs<br/>Epic / Oracle Health FHIR APIs"]
    D3box["D3: Production AI setup - OPEN"]:::open
    subgraph D3 ["D3: Production AI setup - OPEN"]
      D3q{"Who runs the AI and its guardrails?"}
      D3o1["Option 1 - recommended<br/>AWS runs AI: AgentCore + Bedrock Guardrails<br/>Snowflake does research only"]
      D3o2["Option 2<br/>Snowflake runs AI: Cortex Agents<br/>+ Cortex Guard + masking policies"]
      D3o3["Option 3<br/>Gemini on Vertex, agent in FastAPI on ECS<br/>+ Bedrock ApplyGuardrail only"]
      D3q -->|"1"| D3o1
      D3q -->|"2"| D3o2
      D3q -->|"3"| D3o3
    end
    PACR["AgentCore Runtime<br/>research, scribe, reminder agents"]
    PACG["AgentCore Gateway<br/>tools exposed as MCP"]
    PACI["AgentCore Identity + Memory<br/>doctor-scoped credentials"]
    PModels["Bedrock models and/or Gemini on Vertex AI"]
    PGuard["Bedrock Guardrails<br/>PII masking, grounding checks, denied topics"]
    PSnow[("Snowflake Business Critical<br/>guidelines + de-identified cohorts")]
    PPayer["Stedi / Availity<br/>eligibility, claims, prior auth"]
    PDeID["De-identification<br/>Comprehend Medical"]
    PSched["EventBridge Scheduler + Step Functions"]
    PSMS["AWS End User Messaging SMS<br/>no health details, opt-in, STOP, 10DLC"]
    PSec["CloudTrail, CloudWatch/OTel, GuardDuty,<br/>Security Hub, Macie, Secrets Manager"]
    PUsers --> PEdge
    PEdge --> PAPIGW
    PIdP --> PAPIGW
    PAPIGW --> PSvc
    PSvc --> PTiger
    PSvc --> PHL
    PSvc --> PS3
    PEHR <--> PHL
    PSvc --> D3box
    D3box --> D3
    D3o1 --> PACR
    D3o2 --> PSnow
    D3o3 --> PGuard
    PACR --> PACG
    PACR --> PACI
    PACR --> PModels
    PModels --> PGuard
    PACG --> PTiger
    PACG --> PSnow
    PACG --> PPayer
    PHL --> PDeID
    PDeID --> PSnow
    PSvc --> PSched
    PSched --> PSMS
    PSec -.-> PSvc
  end

  %% ================= Wiring: top level =================
  EMR --> D1box
  D1box --> D1
  D1q -->|"hackathon POC"| Hack
  D1q -->|"many users, HIPAA"| Prod
  Hack --> Setup
  HAPI --> Tiger
  HAPI --> Snow
  EMR --> Doc

  Map --> TReg
  Rules --> TReg
  Chunk --> SChunks

  %% Doctor entry points
  Doc -->|"opens patient, picks specialty"| F1in
  Doc -->|"holds mic"| Mic
  Doc -->|"photographs lab report"| F4in
  Doc -->|"types in web chat"| F5in
  Doc -->|"edits reminder manually"| F7edit
  Doc -->|"checks coverage"| F8in
  Nightly --> F6trig
  Nightly --> F7sched

  %% Mic modes
  D4q -->|"Dictate - red"| F2in
  D4q -->|"Ask - blue"| F2bin
  D5q -->|"no"| Q
  D5discard -->|"same transcript"| F2bcls
  D6q -->|"yes, same transcript"| F2ctx
  D6q -->|"no"| D7box
  D7q -->|"research question"| F5agent
  D7q -->|"screening review"| F6trig

  %% Into the approval queue
  F4ins --> Q
  F6val --> Q
  D10q -->|"yes: create ai_suggestion"| Q
  F6ok -.->|"spoken summary"| D9tts

  %% Approval outcomes
  D12q -->|"approve or edit + approve"| F3tx
  D12q -->|"reject"| F3rej
  F3refresh -->|"always"| F1in
  D13rem -->|"yes"| TSched
  D13scr -->|"yes"| F6trig
  F3embed -.->|"searchable later"| F5notes

  %% SMS
  F7send -->|"text"| Pt
  Pt -->|"replies"| D15box
  TSched -->|"due reminders"| F7due
  TSched -.->|"stretch: procedure reminder approved"| F8in

  %% Data reads and writes
  F1q -.-> TReg
  F1q -.-> THyper
  F1q -.-> TAgg
  F1click -.-> THyper
  F2ctx -.-> TReg
  F2ins -.-> TSugg
  D5discard -.-> TSugg
  F4save -.-> Files
  F4ins -.-> TSugg
  F5notes -.-> TNotes
  F5notes -.-> THyper
  D8a -.-> TSugg
  F5guide -.-> SCSS
  F6base -.-> TReg
  F6base -.-> TSched
  F6ctx -.-> TReg
  F6guide -.-> SCSS
  F6val -.-> TSugg
  Q -.-> TSugg
  F3tx -.-> TReg
  F3tx -.-> THyper
  F3tx -.-> TAudit
  F3rej -.-> TAudit
  F3embed -.-> TNotes
  F7edit -.-> TSched
  F7edit -.-> TAudit
  F7send -.-> TSms
  F7hook -.-> TSms
  D15out -.-> TReg
  F8cov -.-> TReg
  F8store -.-> TReg
  D16snow -.-> SCSS
```

## Decision index

| Box | Kind | Branches |
|---|---|---|
| D1: Deployment target | Runtime | Hackathon stack / Production |
| D2: Open stack choices | Open (minor) | Next.js or Vite, SQLAlchemy or SQLModel, function calling or ADK, httpx or connector, host, types generator |
| D3: Production AI setup | **Open** | 1 AWS runs AI (recommended) / 2 Snowflake runs AI / 3 ApplyGuardrail only |
| D4: Toggle mode | Runtime | Dictate / Ask |
| D5: Send as Ask instead? | Runtime | yes: discard suggestions, reclassify as Ask / no: approval queue |
| D6: Send as Dictation instead? | Runtime | yes: run Dictate on same transcript / no: D7 |
| D7: Ask request type | Runtime | research question / screening review |
| D8: Ask sees pending dictation? | **Open** | A include unconfirmed (recommended) / B approved only |
| D9: Came from Ask mode? | Runtime | yes: spoken summary / no |
| D10: Add to plan? | Runtime | yes: new suggestion / no: nothing changes |
| D11: Reminder change needed? | Runtime | propose change / screenings up to date |
| D12: Doctor review | Runtime | approve, edit + approve / reject |
| D13: Post-approval side effects | Runtime | note: embed / reminder: update schedule / screenings: run reminder agent |
| D14: Due and opted in? | Runtime | send SMS / wait |
| D15: Patient replies STOP? | Runtime | opt out |
| D16: Prior-auth question? | Runtime | Cortex Search payer policies / skip |
