export type Severity = "critical" | "watch" | "clear";
export type FindingKind = "injury" | "disease" | "lab";
export type Specialty = "all" | "trauma" | "cardiology" | "gi" | "primary" | "nephrology";

export interface Observation {
  label: string;
  value: string;
}

export interface Finding {
  id: string;
  structureId: string;
  title: string;
  condition: string;
  note: string;
  severity: Severity;
  kind: FindingKind;
  /** Position on the history slider, 0 (oldest) to 100 (now). */
  minute: number;
  specialties: Exclude<Specialty, "all">[];
  meds: string[];
  observations: Observation[];
  /** Where the pin leaves the surface, in patient space: +X is the patient's left, +Y up, +Z anterior. */
  outward: [number, number, number];
  view: "anterior" | "posterior" | "left" | "right" | "superior" | "inferior";
  /** Draws an impact arrow on the pin, for injuries with a known strike direction. */
  impact?: boolean;
}

export interface Reminder {
  id: string;
  title: string;
  detail: string;
  status: "scheduled" | "due" | "sent";
}

export interface ChartNote {
  id: string;
  minute: number;
  text: string;
  findingId?: string;
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  sex: "F" | "M";
  mrn: string;
  summary: string;
  family: string[];
  findings: Finding[];
  notes: ChartNote[];
  reminders: Reminder[];
  smsOptIn: boolean;
  specialties: Exclude<Specialty, "all">[];
}

export type TabKind = "body" | "region" | "timeline" | "queue" | "research" | "lab" | "reminders" | "chat";

export interface WorkTab {
  id: string;
  kind: TabKind;
  patientId: string;
  /** Finding id for region, research id for research, conversation id for chat. */
  refId?: string;
}

export type Agent = "chart" | "research" | "screening";
export type Mode = "auto" | Agent;
/** Where a request went. Navigation is handled outside the three agents. */
export type Route = Agent | "navigate";

export type ChartChange =
  | { type: "add_finding"; finding: Finding }
  | { type: "add_med"; findingId: string; med: string }
  | { type: "add_note"; text: string; findingId?: string }
  | { type: "add_family"; text: string }
  | { type: "update_reminder"; reminderId: string; detail: string };

export type ActionStatus = "pending" | "approved" | "rejected";

/**
 * Everything the agent wants to do waits here until the doctor decides.
 * Searches, opening tabs, and chart writes all go through the same approval.
 */
export interface ProposedAction {
  id: string;
  patientId: string;
  conversationId: string;
  messageId: string;
  agent: Route;
  status: ActionStatus;
  title: string;
  detail: string;
  before?: string;
  after?: string;
  source: string;
  confidence?: string;
  citations?: string[];
  payload:
    | { kind: "search"; corpus: string; query: string; question: string; topic: ResearchTopic }
    | { kind: "open_tab"; tab: TabKind; refId?: string }
    | { kind: "chart_change"; change: ChartChange };
}

export type ResearchTopic = "statin" | "screening" | "diabetes" | "general";

export interface Citation {
  source: string;
  passage: string;
}

export interface ResearchResult {
  id: string;
  patientId: string;
  question: string;
  answer: string;
  basis: string;
  citations: Citation[];
}

export interface Message {
  id: string;
  role: "doctor" | "agent";
  text: string;
  route?: Route;
  routedBy?: "auto" | "manual";
  /** The doctor's request this reply answers; used for re-routing. */
  requestText?: string;
  researchId?: string;
  pending?: boolean;
}

export interface Conversation {
  id: string;
  patientId: string;
  title: string;
  messages: Message[];
}

export interface AuditRow {
  id: string;
  patientId: string;
  action: "Approved" | "Rejected" | "Discarded" | "SMS" | "Opt-out";
  detail: string;
}

export type Layout = "split" | "workspace" | "agent";
