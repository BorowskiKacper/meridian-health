# AI-Powered EMR: Routing Graph

Hackathon build only: no scaling, caching or queues. Each database is shown as a single node.

Changes from draft-1:

- **No Dictate/Ask toggle.** There's one mic, and typed web chat goes to the same place. Every request works like Ask did: Gemini figures out what the doctor wants and routes it. Nothing writes to the chart directly. Chart updates become suggestions the doctor approves.
- **No autonomous AI.** Agents run only when the doctor asks. The nightly reminder-agent job is gone, and an approval no longer triggers the reminder agent on its own. Email sending is still scheduled because it's plain code, not AI.
- **Agent tools are MCP.** Every time an agent reads or proposes something, it goes through an MCP server. Those calls are the **thick arrows**.

How to read it:

- **Yellow dashed box**: a decision. It points into the subgraph with the same name.
- **Orange node**: an MCP server. **Thick arrow**: an MCP tool call.
- **Blue cylinder**: a database.

```mermaid
flowchart LR
  classDef decision fill:#fff3bf,stroke:#f08c00,stroke-width:2px,stroke-dasharray:5 3,color:#000
  classDef mcp fill:#ffd8a8,stroke:#e8590c,stroke-width:3px,color:#000
  classDef db fill:#d0ebff,stroke:#1c7ed6,color:#000
  classDef ext fill:#e9ecef,stroke:#495057,color:#000
  classDef actor fill:#e5dbff,stroke:#7048e8,color:#000

  Doc(["Doctor"]):::actor
  Pt(["Patient"]):::actor
  Web["Web dashboard<br/>3D body, timeline, chat, approval queue"]
  App["Expo app<br/>one mic, camera, approvals"]

  subgraph API ["FastAPI"]
    body["GET /patients/id/body-state<br/>GET /patients/id/regions/region"]
    req["POST /requests<br/>voice or typed"]
    docs["POST /documents<br/>photo of a lab report"]
    sugg["GET /suggestions<br/>POST /suggestions - add to plan<br/>POST /suggestions/approve, /reject"]
    rem["PUT /patients/id/reminders/rid<br/>doctor edits a reminder"]
    runrem["POST /demo/run-reminders<br/>APScheduler or demo button"]
    unsub["GET /email/unsubscribe<br/>signed token opts the patient out"]
    elig["POST /patients/id/eligibility<br/>stretch"]

    D1box["D1: Voice or typed?"]:::decision
    subgraph D1 ["D1: Voice or typed?"]
      D1q{"Did the request come in as audio?"}
    end

    D2box["D2: Request type"]:::decision
    subgraph D2 ["D2: Request type"]
      D2q{"Gemini classifies:<br/>what does the doctor want?"}
    end

    chart["Chart-update agent"]
    research["Research agent"]
    screen["Screening agent"]

    D3box["D3: Approved item is a note?"]:::decision
    subgraph D3 ["D3: Approved item is a note?"]
      D3q{"Is the approved suggestion a note?"}
    end

    D4box["D4: Due and opted in?"]:::decision
    subgraph D4 ["D4: Due and opted in?"]
      D4q{"Reminder due and patient opted in?"}
    end

    D5box["D5: Prior-auth question?"]:::decision
    subgraph D5 ["D5: Prior-auth question?"]
      D5q{"Does the order raise a prior-auth question?"}
    end
  end

  subgraph MCP ["MCP servers"]
    EMRMCP["EMR MCP server - ours<br/>get_patient_context<br/>search_patient_notes<br/>propose_change"]:::mcp
    SnowMCP["Snowflake managed MCP server<br/>search_guidelines - Cortex Search"]:::mcp
  end

  Tiger[("Tiger Data")]:::db
  Snow[("Snowflake")]:::db
  Files[("File storage")]:::db

  Gemini["Gemini API"]:::ext
  EL["ElevenLabs<br/>Scribe STT + TTS"]:::ext
  Resend["Resend<br/>email"]:::ext
  Stedi["Stedi test mode"]:::ext

  %% Clients
  Doc --> Web
  Doc --> App
  Web --> body
  Web --> req
  Web --> sugg
  Web --> rem
  Web --> elig
  App --> req
  App --> docs
  App --> sugg

  %% 3D body view
  body --> Tiger

  %% One entry point for every request
  req --> D1box
  D1box --> D1
  D1q -->|"yes: speech-to-text"| EL
  D1q -->|"no"| D2box
  EL -->|"transcript"| D2box
  D2box --> D2
  D2q -.->|"classify"| Gemini
  D2q -->|"update the chart"| chart
  D2q -->|"clinical question"| research
  D2q -->|"check screenings"| screen

  %% Agents: model calls
  chart -.-> Gemini
  research -.-> Gemini
  screen -.-> Gemini

  %% Agents: MCP tool calls
  chart ==>|"MCP: get_patient_context,<br/>propose_change"| EMRMCP
  research ==>|"MCP: get_patient_context,<br/>search_patient_notes"| EMRMCP
  research ==>|"MCP: search_guidelines"| SnowMCP
  screen ==>|"MCP: get_patient_context,<br/>propose_change"| EMRMCP
  screen ==>|"MCP: search_guidelines"| SnowMCP
  EMRMCP --> Tiger
  SnowMCP --> Snow

  %% Replies
  chart -->|"read-back if voice"| EL
  research -->|"summary if voice"| EL
  screen -->|"summary if voice"| EL

  %% Lab report photo: one Gemini call, no agent, no MCP
  docs --> Files
  docs -->|"vision extraction"| Gemini
  docs -->|"insert suggestions"| Tiger

  %% Approval: the only path that writes to the chart
  sugg --> Tiger
  sugg --> D3box
  D3box --> D3
  D3q -->|"yes: embed, store in Tiger"| Gemini

  %% Reminders + email
  rem --> Tiger
  runrem --> Tiger
  runrem --> D4box
  D4box --> D4
  D4q -->|"yes"| Resend
  Resend -->|"email: clinic sentence and unsubscribe link"| Pt
  Pt -->|"opens unsubscribe link"| unsub
  unsub --> Tiger

  %% Insurance stretch
  elig --> Tiger
  elig --> Stedi
  elig --> D5box
  D5box --> D5
  D5q ==>|"yes - MCP: search_guidelines<br/>over payer policy PDFs"| SnowMCP
  elig -.->|"plain-English summary"| Gemini
```

## When MCP is used

| Caller | MCP server | Tools | Reaches |
|---|---|---|---|
| Chart-update agent | EMR MCP (ours) | `get_patient_context`, `propose_change` | Tiger Data |
| Research agent | EMR MCP (ours) | `get_patient_context`, `search_patient_notes` | Tiger Data |
| Research agent | Snowflake managed MCP | `search_guidelines` | Snowflake |
| Screening agent | EMR MCP (ours) | `get_patient_context`, `propose_change` | Tiger Data |
| Screening agent | Snowflake managed MCP | `search_guidelines` | Snowflake |
| Eligibility endpoint (stretch) | Snowflake managed MCP | `search_guidelines` (payer policies) | Snowflake |

The plain endpoints never use MCP: body view, photo upload, approvals, reminders, email, and the unsubscribe link call the database or vendor API directly.

`propose_change` can only insert into `ai_suggestions`. The only thing that writes to the chart is `POST /suggestions/approve`, after the doctor clicks it.
