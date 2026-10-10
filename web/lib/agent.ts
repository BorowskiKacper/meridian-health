import { altLab, colonScreen, creatinineLab, fibula, ldl190 } from "./data";
import type {
  Agent,
  Citation,
  Mode,
  Patient,
  ProposedAction,
  ResearchResult,
  ResearchTopic,
  Route,
  TabKind,
} from "./types";

/** An action as the agent drafts it; the store assigns ids, status, and ownership. */
export type Draft = Omit<ProposedAction, "id" | "status" | "patientId" | "conversationId" | "messageId">;

export interface Plan {
  route: Route;
  routedBy: "auto" | "manual";
  reply: string;
  drafts: Draft[];
}

export interface Context {
  patient: Patient;
  /** Chart changes still waiting on the doctor, for answers that label them unconfirmed. */
  pending: ProposedAction[];
}

const NAV = /\b(open|show|pull up|bring up|go to)\b/;
const SCREEN = /screen|colonoscopy|up to date|mammogram|eye exam|prevent/;
const QUESTION = /\?\s*$|^(should|what|why|how|is|are|does|do|can|could|would|when)\b/;

const navTargets: [RegExp, TabKind][] = [
  [/timeline|history/, "timeline"],
  [/approv|queue|pending/, "queue"],
  [/lab|panel|report/, "lab"],
  [/reminder|sms/, "reminders"],
  [/body|anatomy|3d/, "body"],
];

export function classify(text: string): Route {
  const lower = text.toLowerCase().trim();
  if (NAV.test(lower) && navTargets.some(([pattern]) => pattern.test(lower))) return "navigate";
  if (SCREEN.test(lower)) return "screening";
  if (QUESTION.test(lower)) return "research";
  return "chart";
}

export function plan(text: string, mode: Mode, ctx: Context): Plan {
  const route: Route = mode === "auto" ? classify(text) : mode;
  const routedBy = mode === "auto" ? "auto" : "manual";
  if (route === "navigate") return { route, routedBy, ...navigate(text, ctx) };
  if (route === "screening") return { route, routedBy, ...screening(ctx) };
  if (route === "research") return { route, routedBy, ...research(text, ctx) };
  return { route, routedBy, ...chart(text, ctx) };
}

function navigate(text: string, ctx: Context): Omit<Plan, "route" | "routedBy"> {
  const lower = text.toLowerCase();
  const tab = navTargets.find(([pattern]) => pattern.test(lower))?.[1] ?? "body";
  const names: Record<TabKind, string> = {
    body: "Body",
    region: "Region",
    timeline: "Timeline",
    queue: "Approvals",
    research: "Research",
    lab: "Lab document",
    reminders: "Reminders",
    chat: "Conversation",
  };
  return {
    reply: `I can open ${names[tab]} for ${ctx.patient.name}. Approve and it opens as a new tab.`,
    drafts: [
      {
        agent: "navigate",
        title: `Open ${names[tab]}`,
        detail: `New tab in the workspace for ${ctx.patient.name}.`,
        source: "Requested in chat",
        payload: { kind: "open_tab", tab },
      },
    ],
  };
}

function chart(text: string, ctx: Context): Omit<Plan, "route" | "routedBy"> {
  const lower = text.toLowerCase();
  const source = "Dictation · transcript";
  const drafts: Draft[] = [];

  if (ctx.patient.id === "nora" && /ldl|lisinopril|mi at/.test(lower)) {
    drafts.push(
      {
        agent: "chart",
        title: "Record LDL 190 mg/dL",
        detail: "New lipid result from this visit.",
        before: "Latest LDL 142 mg/dL, 18 months ago",
        after: "LDL 190 mg/dL today",
        source,
        confidence: "Value within the range a lipid panel reports",
        payload: { kind: "chart_change", change: { type: "add_finding", finding: ldl190 } },
      },
      {
        agent: "chart",
        title: "Start lisinopril 10 mg daily",
        detail: "Medication order from the dictation.",
        before: "No ACE inhibitor",
        after: "Lisinopril 10 mg daily",
        source,
        confidence: "Needs review: indication not stated",
        payload: { kind: "chart_change", change: { type: "add_med", findingId: "ldl-190", med: "Lisinopril 10 mg daily" } },
      },
      {
        agent: "chart",
        title: "Add family history",
        detail: "Father, myocardial infarction at 55.",
        before: ctx.patient.family.join("; "),
        after: "Adds: Father, myocardial infarction at 55",
        source,
        payload: { kind: "chart_change", change: { type: "add_family", text: "Father: myocardial infarction at 55" } },
      },
    );
  } else if (ctx.patient.id === "nora" && /fibula/.test(lower)) {
    drafts.push({
      agent: "chart",
      title: "Add left fibula to the chart",
      detail: "Watch for a fibular fracture.",
      before: "Left fibula not on the chart",
      after: "Possible fibular fracture, watch",
      source,
      confidence: "Bedside exam this visit",
      payload: { kind: "chart_change", change: { type: "add_finding", finding: fibula } },
    });
  } else {
    drafts.push({
      agent: "chart",
      title: "Add a visit note",
      detail: text,
      after: text,
      source,
      payload: { kind: "chart_change", change: { type: "add_note", text } },
    });
  }

  const count = drafts.length === 1 ? "one change" : `${drafts.length} changes`;
  return {
    reply: `I drafted ${count} from your dictation. Nothing is written to the chart until you approve.`,
    drafts,
  };
}

function topicOf(text: string): ResearchTopic {
  const lower = text.toLowerCase();
  if (/statin|ldl|cholesterol|lipid/.test(lower)) return "statin";
  if (/a1c|diabetes|sglt|metformin|glucose|kidney/.test(lower)) return "diabetes";
  return "general";
}

/** The LDL the agent may reason from: approved, or pending from this visit and labeled as such. */
function ldlState(ctx: Context): "approved" | "pending" | "charted" {
  if (ctx.patient.findings.some((f) => f.id === "ldl-190")) return "approved";
  const pending = ctx.pending.some(
    (a) => a.payload.kind === "chart_change" && a.payload.change.type === "add_finding" && a.payload.change.finding.id === "ldl-190",
  );
  return pending ? "pending" : "charted";
}

function deidentified(ctx: Context, topic: ResearchTopic): string {
  const patient = ctx.patient;
  const who = `${patient.sex === "F" ? "Female" : "Male"}, ${patient.age}`;
  if (topic === "statin") {
    return ldlState(ctx) === "charted"
      ? `${who}. LDL 142 mg/dL. Statin indication.`
      : `${who}. LDL 190 mg/dL. Father with MI at 55. Statin indication and intensity.`;
  }
  if (topic === "diabetes") return `${who}. Type 2 diabetes, A1c 8.4%, CKD 3a with albuminuria. Second-line agent.`;
  if (topic === "screening") {
    return patient.id === "nora"
      ? `${who}. First-degree relative with colorectal cancer at 50. Screening start age.`
      : `${who}. Type 2 diabetes, CKD 3a. Retinal and kidney screening intervals.`;
  }
  return `${who}. General clinical question.`;
}

function research(text: string, ctx: Context): Omit<Plan, "route" | "routedBy"> {
  const topic = topicOf(text);
  return {
    reply: "This needs a guideline search. Approve it and only the de-identified query below leaves the chart.",
    drafts: [
      {
        agent: "research",
        title: "Search clinical guidelines",
        detail: "Cortex Search over guidelines and PubMed abstracts.",
        source: "Research agent",
        payload: {
          kind: "search",
          corpus: "Guidelines · USPSTF, AHA/ACC, ADA, PubMed",
          query: deidentified(ctx, topic),
          question: text,
          topic,
        },
      },
    ],
  };
}

function screening(ctx: Context): Omit<Plan, "route" | "routedBy"> {
  return {
    reply: `To review ${ctx.patient.name.split(" ")[0]}'s screenings I need to check current guidance. Approve the search to continue.`,
    drafts: [
      {
        agent: "screening",
        title: "Search screening guidance",
        detail: "Cortex Search over USPSTF recommendations.",
        source: "Screening agent",
        payload: {
          kind: "search",
          corpus: "Guidelines · USPSTF",
          query: deidentified(ctx, "screening"),
          question: "Are screenings up to date?",
          topic: "screening",
        },
      },
    ],
  };
}

const CITE: Record<string, Citation> = {
  statin: {
    source: "2018 AHA/ACC Guideline on the Management of Blood Cholesterol",
    passage: "In patients 20 to 75 years of age with an LDL-C level of 190 mg/dL or higher, maximally tolerated statin therapy is recommended.",
  },
  colon: {
    source: "USPSTF · Colorectal Cancer: Screening (2021)",
    passage: "Screen adults aged 45 to 75. For a first-degree relative diagnosed before 60, start at 40 or 10 years before the relative's diagnosis.",
  },
  eye: {
    source: "ADA Standards of Care in Diabetes · Retinopathy",
    passage: "Adults with type 2 diabetes should have a dilated retinal exam at diagnosis and at least every 1 to 2 years.",
  },
  sglt2: {
    source: "KDIGO 2022 · Diabetes Management in CKD",
    passage: "An SGLT2 inhibitor is recommended for patients with type 2 diabetes, CKD, and an eGFR of 20 mL/min or more.",
  },
};

export interface SearchOutcome {
  result: Omit<ResearchResult, "id">;
  reply: string;
  drafts: Draft[];
}

export function runSearch(action: ProposedAction, ctx: Context): SearchOutcome {
  if (action.payload.kind !== "search") throw new Error("Not a search action");
  const { question, topic } = action.payload;
  const patient = ctx.patient;
  const agent = action.agent as Agent;

  if (topic === "statin") {
    const ldl = ldlState(ctx);
    if (ldl === "charted") {
      return {
        result: {
          patientId: patient.id,
          question,
          basis: "Based on the charted LDL of 142 mg/dL from 18 months ago.",
          answer:
            "At 142 mg/dL the statin decision rests on 10-year cardiovascular risk, not LDL alone. A current lipid panel would settle it.",
          citations: [CITE.statin],
        },
        reply: "The charted LDL is below the direct statin threshold. If you have a newer value, dictate it and ask again.",
        drafts: [],
      };
    }
    const basis =
      ldl === "approved"
        ? "Based on the approved LDL of 190 mg/dL."
        : "Based on an unconfirmed LDL of 190 mg/dL from this visit's pending dictation.";
    return {
      result: {
        patientId: patient.id,
        question,
        basis,
        answer:
          "An LDL at or above 190 mg/dL is a direct indication for a high-intensity statin, without needing a risk score. A father with a myocardial infarction at 55 adds to the case.",
        citations: [CITE.statin],
      },
      reply: "Here is what the guidelines say. I can add a statin to the plan if you approve it.",
      drafts: [
        {
          agent,
          title: "Add a high-intensity statin to the plan",
          detail: "Dose not chosen. Discuss with the patient.",
          before: "No statin",
          after: "High-intensity statin, dose to be chosen",
          source: "Research agent",
          citations: [CITE.statin.source],
          payload: {
            kind: "chart_change",
            change: { type: "add_med", findingId: "ldl-190", med: "High-intensity statin, dose not chosen" },
          },
        },
      ],
    };
  }

  if (topic === "screening" && patient.id === "nora") {
    return {
      result: {
        patientId: patient.id,
        question,
        basis: "Based on age 47, father with colorectal cancer at 50, and no colonoscopy on the chart.",
        answer: "Screenings are not up to date. With a first-degree relative diagnosed at 50, colorectal screening should have started at 40.",
        citations: [CITE.colon],
      },
      reply: "Colorectal screening is overdue. I drafted the reminder change and the chart entry.",
      drafts: [
        {
          agent,
          title: "Move colorectal screening to age 40",
          detail: "Reminder schedule change.",
          before: "Average-risk start at 45",
          after: "Overdue. Start moved to 40 for a first-degree relative diagnosed at 50.",
          source: "Screening agent",
          citations: [CITE.colon.source],
          payload: {
            kind: "chart_change",
            change: { type: "update_reminder", reminderId: "colon", detail: "Overdue. Start moved from 45 to 40 for a first-degree relative diagnosed at 50." },
          },
        },
        {
          agent,
          title: "Flag colorectal screening on the chart",
          detail: "Adds the colon to the body view.",
          after: "Colorectal screening overdue",
          source: "Screening agent",
          citations: [CITE.colon.source],
          payload: { kind: "chart_change", change: { type: "add_finding", finding: colonScreen } },
        },
      ],
    };
  }

  if (topic === "screening") {
    return {
      result: {
        patientId: patient.id,
        question,
        basis: "Based on type 2 diabetes, CKD 3a, and a retinal exam 14 months ago.",
        answer: "The retinal exam is due. Kidney screening is current: eGFR and UACR were checked this year.",
        citations: [CITE.eye],
      },
      reply: "One screening is due. I drafted the reminder update.",
      drafts: [
        {
          agent,
          title: "Mark the diabetic eye exam due now",
          detail: "Reminder schedule change.",
          before: "Annual retinal exam",
          after: "Due now. Last exam 14 months ago.",
          source: "Screening agent",
          citations: [CITE.eye.source],
          payload: { kind: "chart_change", change: { type: "update_reminder", reminderId: "eye", detail: "Due now. Last exam 14 months ago." } },
        },
      ],
    };
  }

  if (topic === "diabetes") {
    return {
      result: {
        patientId: patient.id,
        question,
        basis: "Based on A1c 8.4%, eGFR 52, and UACR 64 mg/g.",
        answer: "With CKD and albuminuria, an SGLT2 inhibitor is the recommended addition. It lowers glucose and slows kidney decline.",
        citations: [CITE.sglt2],
      },
      reply: "The guidance points to an SGLT2 inhibitor. I can add it to the plan if you approve.",
      drafts: [
        {
          agent,
          title: "Add an SGLT2 inhibitor to the plan",
          detail: "Agent not chosen.",
          before: "Metformin only",
          after: "Metformin and an SGLT2 inhibitor",
          source: "Research agent",
          citations: [CITE.sglt2.source],
          payload: { kind: "chart_change", change: { type: "add_med", findingId: "a1c", med: "SGLT2 inhibitor, agent not chosen" } },
        },
      ],
    };
  }

  return {
    result: {
      patientId: patient.id,
      question,
      basis: "Based on the approved chart.",
      answer: "The cached guideline index has no passage that answers this directly. A live search would be needed.",
      citations: [],
    },
    reply: "I could not find a cited answer in the cached index.",
    drafts: [],
  };
}

export function labDrafts(patient: Patient): Draft[] {
  const source = "Lab photo · vision extraction";
  return [
    {
      agent: "chart",
      title: "Record ALT 88 U/L",
      detail: "Flagged high on the paper panel.",
      before: "No ALT on the chart",
      after: "ALT 88 U/L, high",
      source,
      confidence: "Units checked. Read clearly.",
      payload: { kind: "chart_change", change: { type: "add_finding", finding: { ...altLab, specialties: patient.specialties.includes("gi") ? altLab.specialties : ["primary"] } } },
    },
    {
      agent: "chart",
      title: "Record creatinine 1.3 mg/dL",
      detail: "Flagged high on the paper panel.",
      before: "No creatinine from today",
      after: "Creatinine 1.3 mg/dL, high",
      source,
      confidence: "Units checked. Read clearly.",
      payload: { kind: "chart_change", change: { type: "add_finding", finding: { ...creatinineLab, id: `creatinine-${patient.id}` } } },
    },
  ];
}
