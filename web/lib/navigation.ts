import type { Patient, TabKind } from "./types";

// Mirror of parse_navigation in backend/app/mcp/workspace_tools.py; keep the two in sync.
const ALIASES: Record<string, TabKind> = {
  chart: "overview", overview: "overview", "patient chart": "overview",
  information: "overview", info: "overview", profile: "overview", record: "overview",
  lab: "lab", visit: "visit", reminders: "reminders",
  vitals: "vitals", "vital signs": "vitals", trends: "vitals",
  "blood pressure": "vitals", "blood pressure trends": "vitals", "weight trends": "vitals",
  problems: "problems", "problem list": "problems",
  medications: "medications", "medication list": "medications", meds: "medications",
  allergies: "allergies", labs: "lab", "lab results": "lab", diagnostics: "lab",
  "visit draft": "visit", "follow-up": "reminders", "follow up": "reminders",
  history: "history", timeline: "timeline", body: "body", "3d view": "body", queue: "queue",
};
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const VIEW = `(?:the\\s+)?(?<view>${Object.keys(ALIASES).sort((a, b) => b.length - a.length).map(escape).join("|")})(?:\\s+(?:tab|view|page|screen))?`;
const COMMAND = /^(?:(?:please|(?:can|could|would) you(?: please)?)\s+)?(?:open(?: up)?|show(?: me)?|display|bring up|pull up|take me to|(?:switch|go|navigate|change) to|(?:i\s+(?:want|would like)\s+to\s+|i[’']d like to\s+|let me\s+)?see)\s+(.+?)(?:\s+on\s+(?:my|the)\s+(?:laptop|desktop))?[.!?]?$/i;
const MIXED = /\b(and|research|diagnose|change|update|set|start|stop|order|prescribe|delete|increase|decrease)\b/i;
const VIEW_FIRST = new RegExp(`^${VIEW}(?:\\s+(?:for|of)\\s+(?<patient>.+))?$`, "i");
const PATIENT_FIRST = new RegExp(`^(?<patient>.+?)(?:[’']s\\s+|\\s+)${VIEW}$`, "i");

/** A pure "open this chart section" request, optionally naming a patient; null for anything else. */
export function parseNavigation(text: string): { view: TabKind; patient: string | null } | null {
  const request = COMMAND.exec(text.trim())?.[1];
  if (!request || MIXED.test(request)) return null;
  const match = VIEW_FIRST.exec(request) ?? PATIENT_FIRST.exec(request);
  if (!match?.groups) return null;
  let patient = match.groups.patient?.replace(/^patient\s+/i, "").trim() || null;
  if (patient && ["his", "her", "their", "this patient", "the patient", "my patient"].includes(patient.toLowerCase())) patient = null;
  else if (patient && (patient.length > 200 || !/^[\w\s\-'’]+$/.test(patient))) return null;
  return { view: ALIASES[match.groups.view.toLowerCase()]!, patient };
}

/** The one loaded patient whose full, first, or last name matches; undefined when none or several do. */
export function findPatient(patients: Record<string, Patient>, query: string): Patient | undefined {
  const q = query.trim().toLowerCase();
  const matches = Object.values(patients).filter((p) => p.name.toLowerCase() === q || p.name.toLowerCase().split(/\s+/).includes(q));
  return matches.length === 1 ? matches[0] : undefined;
}
