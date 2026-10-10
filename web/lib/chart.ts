import { labPanel, NOW_MINUTE } from "./data";
import type {
  BodyState,
  ChartPatient,
  RegionChart,
  ReminderRow,
  SuggestionRow,
  TimelineEvent,
} from "./api";
import {
  getBodyState,
  getRegion,
  listPatients,
  listReminders,
  listSuggestions,
} from "./api";
import type { ChartNote, Finding, Patient, ProposedAction, Reminder, Specialty } from "./types";

const CHART_SPECIALTIES = ["cardiology", "gastroenterology", "pulmonology"] as const;

const ATLAS: Record<string, Pick<Finding, "structureId" | "outward" | "view">> = {
  heart: { structureId: "cardiovascular.heart", outward: [0.35, 0.55, 0.85], view: "anterior" },
  lung: { structureId: "visceral.left_lung", outward: [1, 0.15, 0.55], view: "left" },
  colon: { structureId: "visceral.colon", outward: [0.25, -0.35, 0.95], view: "anterior" },
};

export interface WorkspaceChart {
  patients: Patient[];
  actions: ProposedAction[];
}

export async function reloadPatient(patientId: string) {
  const { patients } = await listPatients();
  const directory = patients.find((patient) => patient.id === patientId);
  if (!directory) throw new Error("Patient was not found.");
  return loadPatient(directory);
}

export async function loadWorkspace(): Promise<WorkspaceChart> {
  const { patients } = await listPatients();
  const loaded = await Promise.all(patients.map(loadPatient));
  return {
    patients: loaded.map((item) => item.patient),
    actions: loaded.flatMap((item) => item.actions),
  };
}

export async function loadPatient(directory: ChartPatient): Promise<{ patient: Patient; actions: ProposedAction[] }> {
  const [states, reminders, suggestions] = await Promise.all([
    Promise.all(CHART_SPECIALTIES.map((specialty) => getBodyState(directory.id, specialty))),
    listReminders(directory.id),
    listSuggestions(directory.id),
  ]);
  const bySpecialty = Object.fromEntries(CHART_SPECIALTIES.map((specialty, index) => [specialty, states[index]!])) as Record<
    (typeof CHART_SPECIALTIES)[number],
    BodyState
  >;
  const focus = new Map<string, Exclude<Specialty, "all">[]>();
  for (const specialty of CHART_SPECIALTIES) {
    for (const region of bySpecialty[specialty].regions) {
      if (region.emphasis !== "focus") continue;
      const current = focus.get(region.region_key) ?? [];
      current.push(specialty);
      focus.set(region.region_key, current);
    }
  }
  const regions = bySpecialty.cardiology.regions;
  const details = await Promise.all(regions.map((region) => getRegion(directory.id, region.region_key)));
  const timeline = bySpecialty.cardiology.timeline;
  const span = timeSpan(timeline);
  const findings = regions
    .map((region, index) => findingFromRegion(region.region_key, region.mesh_name, details[index]!, focus.get(region.region_key) ?? [], span))
    .filter((finding): finding is Finding => finding !== null);
  const notes = timeline
    .filter((event) => event.kind !== "condition")
    .map((event) => noteFromEvent(event, span));
  const patient: Patient = {
    id: directory.id,
    name: directory.display_name,
    age: directory.age,
    sex: directory.sex === "male" ? "M" : "F",
    mrn: directory.id.slice(0, 8).toUpperCase(),
    summary: summaryFor(findings),
    family: directory.family_history.map(familyLine),
    findings,
    notes,
    reminders: reminders.reminders.map(reminderFromRow),
    smsOptIn: directory.sms_opt_in,
    phone: directory.phone_e164,
    specialties: [...CHART_SPECIALTIES],
  };
  return { patient, actions: suggestions.map((row) => suggestionAction(row)) };
}

export function suggestionAction(row: SuggestionRow, link?: { conversationId: string; messageId: string }): ProposedAction {
  return {
    id: row.id,
    patientId: row.patient_id,
    conversationId: link?.conversationId ?? "",
    messageId: link?.messageId ?? "",
    agent: row.source === "reminder_agent" ? "screening" : row.source === "research_add_to_plan" ? "research" : "chart",
    status: row.status,
    title: row.reason || row.kind,
    detail: `${row.kind.replaceAll("_", " ")} · ${row.target_table.replaceAll("_", " ")}`,
    before: formatPatch(row.before),
    after: formatPatch(row.after),
    source: row.source,
    confidence: Number.isFinite(row.confidence) ? `${Math.round(row.confidence * 100)}%` : undefined,
    citations: row.citations.map((citation) => citation.title || citation.source_id || "").filter(Boolean),
    payload: { kind: "chart_change", change: { type: "add_note", text: row.reason } },
  };
}

export function labReportFile(patientName: string): File {
  const lines = [
    labPanel.lab,
    labPanel.collected,
    `${labPanel.title} · Patient: ${patientName}`,
    ...labPanel.rows.map((row) => [row.test, row.value, row.unit, row.range, row.flag].join("\t")),
  ];
  return new File([lines.join("\n")], "lab-report.txt", { type: "text/plain" });
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function summaryFor(findings: Finding[]): string {
  if (!findings.length) return "No conditions on the chart.";
  return findings.map((finding) => finding.condition).join(". ") + ".";
}

function familyLine(row: ChartPatient["family_history"][number]): string {
  const who = row.relationship.slice(0, 1).toUpperCase() + row.relationship.slice(1);
  return `${who}: ${row.condition} at ${row.age_at_diagnosis}`;
}

function findingFromRegion(
  regionKey: string,
  meshName: string,
  detail: RegionChart,
  specialties: Exclude<Specialty, "all">[],
  span: { start: number; end: number },
): Finding | null {
  if (!detail.conditions.length && !detail.medications.length && !detail.observations.length) return null;
  const atlas = ATLAS[regionKey] ?? {
    structureId: regionKey,
    outward: [0, 0.2, 1] as [number, number, number],
    view: "anterior" as const,
  };
  const active = detail.conditions.some((condition) => condition.status === "active");
  const dated = [
    ...detail.conditions.map((condition) => condition.onset_date),
    ...detail.observations.map((observation) => observation.observed_at),
  ].filter((value): value is string => Boolean(value));
  const earliest = dated.sort()[0];
  return {
    id: regionKey,
    structureId: atlas.structureId,
    title: detail.conditions[0]?.name ?? meshName,
    condition: detail.conditions.map((condition) => condition.name).join(", ") || meshName,
    note: detail.conditions.map((condition) => `${condition.name} is ${condition.status}.`).join(" ") || "Charted on this region.",
    severity: active || detail.observations.length > 0 ? "watch" : "clear",
    kind: detail.conditions.length ? "disease" : "lab",
    minute: earliest ? minuteAt(earliest, span) : NOW_MINUTE,
    when: earliest ? formatWhen(earliest) : undefined,
    specialties,
    meds: detail.medications.map((medication) =>
      [medication.name, medication.dose, medication.route, medication.frequency].filter(Boolean).join(" "),
    ),
    observations: detail.observations.map((observation) => ({
      label: observation.name,
      value: `${observation.value} ${observation.unit}`.trim(),
    })),
    outward: atlas.outward,
    view: atlas.view,
  };
}

function noteFromEvent(event: TimelineEvent, span: { start: number; end: number }): ChartNote {
  return {
    id: `${event.kind}-${event.at}-${event.label}`,
    minute: minuteAt(event.at, span),
    when: formatWhen(event.at),
    text: event.label,
  };
}

function reminderFromRow(row: ReminderRow): Reminder {
  const due = row.due_on.slice(0, 10) <= todayIso();
  const status = row.status === "scheduled" && due ? "due" : row.status;
  return {
    id: row.id,
    title: row.name,
    detail: `Due ${row.due_on.slice(0, 10)}`,
    status: status as Reminder["status"],
  };
}

function formatPatch(patch: Record<string, unknown> | undefined): string | undefined {
  if (!patch || !Object.keys(patch).length) return undefined;
  return Object.entries(patch)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
    .join(", ");
}

function timeSpan(events: TimelineEvent[]): { start: number; end: number } {
  const stamps = events.map((event) => Date.parse(event.at)).filter((value) => !Number.isNaN(value));
  const now = Date.now();
  if (!stamps.length) return { start: now, end: now };
  return { start: Math.min(...stamps), end: Math.max(...stamps, now) };
}

function minuteAt(iso: string, span: { start: number; end: number }): number {
  const at = Date.parse(iso);
  if (Number.isNaN(at) || span.end <= span.start) return NOW_MINUTE;
  return Math.max(0, Math.min(NOW_MINUTE, Math.round(((at - span.start) / (span.end - span.start)) * NOW_MINUTE)));
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}
