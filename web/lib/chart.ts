import { placeOnAtlas } from "./atlas";
import { formatMonth, minuteAt, NOW_MINUTE } from "./data";
import { isConcerning } from "./reference";
import type { ChartPatient, ChartSeries, PatientChart, SuggestionRow } from "./api";
import { getChart, searchPatients, listSuggestions } from "./api";
import type {
  Allergy,
  ChartNote,
  Finding,
  Medication,
  Observation,
  Patient,
  Problem,
  ProposedAction,
  Reminder,
  Severity,
  Trend,
} from "./types";

export interface WorkspaceChart {
  patients: Patient[];
  actions: ProposedAction[];
}

export async function reloadPatient(patientId: string) {
  return loadPatient({ id: patientId });
}

export async function loadWorkspace(): Promise<WorkspaceChart> {
  const { patients } = await searchPatients("", 1);
  const loaded = await Promise.all(patients.map(loadPatient));
  return {
    patients: loaded.map((item) => item.patient),
    actions: loaded.flatMap((item) => item.actions),
  };
}

export async function loadPatient(directory: Pick<ChartPatient, "id">): Promise<{ patient: Patient; actions: ProposedAction[] }> {
  const [chart, suggestions] = await Promise.all([getChart(directory.id), listSuggestions(directory.id)]);
  return { patient: patientFromChart(chart), actions: suggestions.map((row) => suggestionAction(row)) };
}

export function patientFromChart(chart: PatientChart): Patient {
  const { patient: directory } = chart;
  const span = timeSpan(chart);
  const problems: Problem[] = chart.conditions.map((row) => ({
    id: row.id,
    name: row.name,
    status: row.status,
    onset: row.onset_date ?? undefined,
    regionKey: row.body_region_key,
  }));
  const medications: Medication[] = chart.medications.map((row) => ({
    id: row.id,
    name: row.name,
    dose: row.dose,
    route: row.route,
    frequency: row.frequency,
    status: row.status,
    start: row.start_date ?? undefined,
    regionKey: row.body_region_key,
  }));
  const specialties = uniqueSpecialties(chart);
  const findings = chart.regions
    .map((region) =>
      findingFromRegion(
        region,
        problems.filter((problem) => problem.regionKey === region.region_key),
        medications.filter((medication) => medication.regionKey === region.region_key),
        chart.series.filter((series) => series.body_region_key === region.region_key),
        span,
      ),
    )
    .filter((finding): finding is Finding => finding !== null)
    .sort((a, b) => severityRank(a.severity) - severityRank(b.severity) || a.title.localeCompare(b.title));

  const notes: ChartNote[] = [
    ...chart.encounters.map<ChartNote>((row) => ({
      id: row.id,
      minute: minuteAt(row.occurred_at, span),
      at: row.occurred_at,
      when: formatMonth(row.occurred_at),
      text: row.summary,
      kind: row.encounter_type === "procedure" ? "procedure" : "visit",
    })),
    ...chart.notes.map<ChartNote>((row) => ({
      id: row.id,
      minute: minuteAt(row.visit_date ? `${row.visit_date}T12:00:00` : row.created_at, span),
      at: row.visit_date ? `${row.visit_date}T12:00:00` : row.created_at,
      when: formatMonth(row.visit_date ? `${row.visit_date}T12:00:00` : row.created_at),
      text: row.body,
      kind: "note",
    })),
    ...chart.medications
      .filter((row) => row.start_date)
      .map<ChartNote>((row) => ({
        id: `med-${row.id}`,
        minute: minuteAt(row.start_date!, span),
        at: row.start_date!,
        when: formatMonth(row.start_date!),
        text: `${row.name} ${row.dose} ${row.frequency} started${row.status === "stopped" ? ", since stopped" : ""}`,
        kind: "medication",
        findingId: findings.some((finding) => finding.regionKey === row.body_region_key) ? row.body_region_key : undefined,
      })),
  ];

  const upcoming = chart.appointments.find((row) => row.status === "scheduled" && Date.parse(row.starts_at) >= Date.now() - 86_400_000);

  return {
    id: directory.id,
    name: directory.display_name,
    age: directory.age,
    sex: directory.sex?.trim() || "Not recorded",
    dob: directory.date_of_birth ?? undefined,
    mrn: `R-${directory.id.replaceAll("-", "").slice(0, 6).toUpperCase()}`,
    summary: summaryFor(problems, chart),
    family: directory.family_history.map(familyLine),
    allergies: directory.allergies.map(allergyFromRow),
    problems,
    medications,
    trends: chart.series.map(trendFromSeries),
    findings,
    chartRegions: chart.regions.map((region) => ({ key: region.region_key, label: region.display_name })),
    notes,
    encounters: chart.encounters.map((row) => ({ id: row.id, type: row.encounter_type, at: row.occurred_at, summary: row.summary })),
    appointments: chart.appointments.map((row) => ({ id: row.id, at: row.starts_at, endsAt: row.ends_at, reason: row.reason, status: row.status })),
    reminders: chart.reminders.map(reminderFromRow),
    nextAppointment: upcoming ? { at: upcoming.starts_at, reason: upcoming.reason } : undefined,
    coverage: chart.coverage
      ? {
          payer: chart.coverage.payer_name,
          plan: chart.coverage.plan_name,
          active: chart.coverage.active,
          copay: chart.coverage.copay,
          deductibleRemaining: chart.coverage.deductible_remaining,
        }
      : undefined,
    pendingCount: chart.pending_suggestions,
    span,
    emailOptIn: directory.email_opt_in,
    email: directory.email,
    unsubscribeToken: directory.unsubscribe_token,
    specialties,
  };
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

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function trendFromSeries(item: ChartSeries): Trend {
  return {
    name: item.name,
    unit: item.unit,
    points: item.points
      .filter((point) => Number.isFinite(point.value) && Number.isFinite(Date.parse(point.at)))
      .map((point) => ({ id: point.id, at: point.at, value: point.value, source: point.source, documentId: point.document_id ?? undefined }))
      .sort((a, b) => Date.parse(a.at) - Date.parse(b.at)),
  };
}

function uniqueSpecialties(chart: PatientChart): string[] {
  const seen = new Set<string>();
  for (const region of chart.regions) for (const specialty of region.specialties) seen.add(specialty);
  const others = [...seen].filter((specialty) => specialty !== "primary_care").sort();
  // The practice's own view leads.
  return seen.has("primary_care") ? ["primary_care", ...others] : others;
}

function summaryFor(problems: Problem[], chart: PatientChart): string {
  const active = problems.filter((problem) => problem.status !== "resolved").map((problem) => problem.name);
  const lastVisit = chart.encounters.at(-1);
  const parts: string[] = [];
  if (active.length) parts.push(active.join(", ") + ".");
  else parts.push("No active problems on the chart.");
  if (lastVisit) parts.push(`Last seen ${formatMonth(lastVisit.occurred_at)}: ${lastVisit.summary}`);
  return parts.join(" ");
}

function familyLine(row: ChartPatient["family_history"][number]): string {
  const who = row.relationship.slice(0, 1).toUpperCase() + row.relationship.slice(1);
  return `${who}: ${row.condition} at ${row.age_at_diagnosis}`;
}

function allergyFromRow(row: ChartPatient["allergies"][number]): Allergy {
  return {
    id: row.id,
    substance: row.substance,
    category: row.category,
    reaction: row.reaction,
    severity: row.severity,
    status: row.status,
    recordedOn: row.recorded_on ?? undefined,
  };
}

function severityRank(severity: Severity): number {
  return severity === "critical" ? 0 : severity === "watch" ? 1 : 2;
}

function findingFromRegion(
  region: PatientChart["regions"][number],
  problems: Problem[],
  medications: Medication[],
  series: ChartSeries[],
  span: { start: number; end: number },
): Finding | null {
  if (region.region_key === "general" || (!problems.length && !medications.length && !series.length)) return null;
  const placement = placeOnAtlas(region.mesh_name, region.region_key);
  const trends: Trend[] = series.map(trendFromSeries);
  const latest: Observation[] = trends.flatMap((trend) => {
    const point = trend.points.at(-1);
    return point ? [{ label: trend.name, value: `${point.value} ${trend.unit}`.trim(), at: point.at }] : [];
  });
  const dated = [
    ...problems.map((problem) => problem.onset),
    ...series.flatMap((item) => item.points.map((point) => point.at)),
    ...medications.map((medication) => medication.start),
  ].filter((value): value is string => Boolean(value));
  const earliest = dated.sort()[0];
  const active = problems.filter((problem) => problem.status === "active");
  const concerning = trends.some((trend) => {
    const last = trend.points.at(-1);
    return last ? isConcerning(trend.name, last.value) : false;
  });
  // The API supplies no critical-result flag. A display threshold cannot establish urgency.
  const severity: Severity = active.length || concerning ? "watch" : "clear";
  const title = problems.find((problem) => problem.status === "active")?.name ?? problems[0]?.name ?? region.display_name;
  return {
    id: region.region_key,
    regionKey: region.region_key,
    structureId: placement.structureId,
    title,
    condition: problems.map((problem) => problem.name).join(", ") || `${region.display_name} · labs only`,
    note: noteFor(problems, trends),
    severity,
    kind: problems.length ? "disease" : "lab",
    minute: earliest ? minuteAt(earliest, span) : NOW_MINUTE,
    at: earliest ?? new Date(span.end).toISOString(),
    when: earliest ? formatMonth(earliest) : undefined,
    specialties: region.specialties,
    problems,
    meds: medications
      .filter((medication) => medication.status === "active")
      .map((medication) => [medication.name, medication.dose, medication.route, medication.frequency].filter(Boolean).join(" ")),
    observations: latest,
    trends,
    outward: placement.outward,
    view: placement.view,
  };
}

function noteFor(problems: Problem[], trends: Trend[]): string {
  const parts = problems.map((problem) => `${problem.name} is ${problem.status}${problem.onset ? ` since ${formatMonth(problem.onset)}` : ""}.`);
  for (const trend of trends) {
    const points = trend.points;
    if (points.length < 2) continue;
    const first = points[0]!.value;
    const last = points.at(-1)!.value;
    const direction = last > first ? "rising" : last < first ? "falling" : "flat";
    parts.push(`${trend.name} ${direction}, ${first} to ${last} ${trend.unit} over ${points.length} results.`);
  }
  return parts.join(" ") || "Charted on this region.";
}

function reminderFromRow(row: PatientChart["reminders"][number]): Reminder {
  const overdue = row.due_on <= todayIso();
  const status = row.status === "scheduled" && overdue ? "due" : row.status;
  const detail =
    row.status === "sent" && overdue
      ? `Reminded, not yet scheduled · was due ${row.due_on}`
      : overdue && row.status === "scheduled"
        ? `Overdue since ${row.due_on}`
        : `Due ${row.due_on}`;
  return {
    id: row.id,
    title: row.name,
    detail,
    dueOn: row.due_on,
    status: status as Reminder["status"],
    rule: row.rule ? { name: row.rule.name, baselineAge: row.rule.baseline_age, source: row.rule.guideline_source_id } : undefined,
  };
}

function formatPatch(patch: Record<string, unknown> | undefined): string | undefined {
  if (!patch || !Object.keys(patch).length) return undefined;
  return Object.entries(patch)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
    .join(", ");
}

function timeSpan(chart: PatientChart): { start: number; end: number } {
  const stamps = [
    ...chart.conditions.map((row) => row.onset_date),
    ...chart.medications.map((row) => row.start_date),
    ...chart.encounters.map((row) => row.occurred_at),
    ...chart.notes.flatMap((row) => [row.created_at, row.visit_date ? `${row.visit_date}T12:00:00` : row.created_at]),
    ...chart.series.flatMap((row) => row.points.map((point) => point.at)),
  ]
    .map((value) => (value ? Date.parse(value) : Number.NaN))
    .filter((value) => !Number.isNaN(value));
  const now = Date.now();
  if (!stamps.length) return { start: now, end: now };
  return { start: Math.min(...stamps), end: Math.max(...stamps, now) };
}
