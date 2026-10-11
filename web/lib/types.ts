export type Severity = "critical" | "watch" | "clear";
export type FindingKind = "injury" | "disease" | "lab";
/** Specialty keys come from the clinic's specialty_focus table; "all" is the unfiltered view. */
export type Specialty = string;

export interface Observation {
  label: string;
  value: string;
  at?: string;
}

export interface TrendPoint {
  id?: string;
  at: string;
  value: number;
  source?: string;
  documentId?: string;
}

export interface Trend {
  name: string;
  unit: string;
  points: TrendPoint[];
}

export interface Problem {
  id: string;
  name: string;
  status: string;
  onset?: string;
  regionKey: string;
}

export interface Medication {
  id: string;
  name: string;
  dose: string;
  route: string;
  frequency: string;
  status: string;
  start?: string;
  regionKey: string;
}

export interface Allergy {
  id: string;
  substance: string;
  category: string;
  reaction: string;
  severity: string;
  status: string;
  recordedOn?: string;
}

export interface Finding {
  id: string;
  /** Chart region key; also the finding id. */
  regionKey: string;
  structureId: string;
  title: string;
  condition: string;
  note: string;
  severity: Severity;
  kind: FindingKind;
  /** Position on the history slider, 0 (oldest in the chart) to 100 (now). */
  minute: number;
  /** When this region first entered the chart, ISO 8601. */
  at: string;
  specialties: Specialty[];
  problems: Problem[];
  meds: string[];
  /** Latest value of each series on this region. */
  observations: Observation[];
  trends: Trend[];
  /** Where the pin leaves the surface, in patient space: +X is the patient's left, +Y up, +Z anterior. */
  outward: [number, number, number];
  view: "anterior" | "posterior" | "left" | "right" | "superior" | "inferior";
  /** Draws an impact arrow on the pin, for injuries with a known strike direction. */
  impact?: boolean;
  /** Calendar label from the chart. The slider still uses `minute`. */
  when?: string;
}

export interface Reminder {
  id: string;
  title: string;
  detail: string;
  dueOn: string;
  status: "scheduled" | "due" | "sent" | "paused" | "done";
  rule?: { name: string; baselineAge: number; source: string };
}

export interface ChartNote {
  id: string;
  minute: number;
  at: string;
  text: string;
  kind: "note" | "visit" | "procedure" | "medication";
  findingId?: string;
  when?: string;
}

export interface Coverage {
  payer: string;
  plan: string;
  active: boolean;
  copay: number;
  deductibleRemaining: number;
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  sex: string;
  dob?: string;
  mrn: string;
  summary: string;
  family: string[];
  allergies: Allergy[];
  problems: Problem[];
  medications: Medication[];
  trends: Trend[];
  findings: Finding[];
  chartRegions: { key: string; label: string }[];
  notes: ChartNote[];
  encounters: { id: string; type: string; at: string; summary: string }[];
  appointments: { id: string; at: string; endsAt: string; reason: string; status: string }[];
  reminders: Reminder[];
  nextAppointment?: { at: string; reason: string };
  coverage?: Coverage;
  pendingCount: number;
  /** Oldest and newest instant on the chart, ms since epoch. The slider maps 0..100 onto this. */
  span: { start: number; end: number };
  emailOptIn: boolean;
  email?: string;
  unsubscribeToken?: string;
  specialties: Specialty[];
}

export type TabKind = "overview" | "vitals" | "visit" | "problems" | "medications" | "allergies" | "body" | "region" | "timeline" | "queue" | "research" | "lab" | "reminders" | "history";

export interface WorkTab {
  id: string;
  kind: TabKind;
  patientId: string;
  /** Finding id for region, research id for research. */
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
  id?: string;
  tier?: string;
  locator?: string;
}

export interface ResearchResult {
  id: string;
  patientId: string | null;
  question: string;
  answer: string;
  basis: string;
  citations: Citation[];
  sections?: { title: string; text: string; source_ids: string[] }[];
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
  error?: boolean;
  audioBase64?: string;
}

export interface Conversation {
  id: string;
  patientId: string | null;
  title: string;
  messages: Message[];
}

export interface AuditRow {
  id: string;
  patientId: string;
  action: "Approved" | "Rejected" | "Discarded" | "Email" | "Opt-out";
  detail: string;
}

export type Layout = "split" | "workspace" | "agent";
