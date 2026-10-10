const API_ROOT = "/backend-api";

export interface Capabilities { assistant: boolean; speech: boolean; lab_extraction: boolean }
export function getCapabilities() { return api<Capabilities>("/capabilities"); }

export interface VisitDraftData {
  visit_date: string;
  reason: string;
  assessment: string;
  plan: string;
  saved_at?: string;
}

export interface ReviewData {
  saved_at: string;
  stale: boolean;
  medication_use: Record<string, "taking" | "not_taking" | "unknown">;
  note: string;
}

export interface EntryState {
  draft: VisitDraftData | null;
  medications: ReviewData | null;
  allergies: ReviewData | null;
  versions: { medications: string; allergies: string };
}

export function getEntryState(patientId: string) {
  return api<EntryState>(`/patients/${patientId}/entry-state`);
}

export function saveChartEntry(patientId: string, path: string, data: Record<string, unknown>, submissionId: string, method = "POST") {
  return api<{ saved: boolean; saved_at: string }>(`/patients/${patientId}/${path}`, {
    method, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, submission_id: submissionId }),
  });
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export interface AllergyRow {
  id: string;
  substance: string;
  category: "drug" | "food" | "environmental" | "nkda" | string;
  reaction: string;
  severity: "anaphylaxis" | "severe" | "moderate" | "mild" | "none" | string;
  status: string;
  recorded_on: string | null;
}

export interface ChartPatient {
  id: string;
  display_name: string;
  date_of_birth: string | null;
  age: number;
  sex: string;
  sms_opt_in: boolean;
  phone_e164: string;
  family_history: { relationship: string; condition: string; age_at_diagnosis: number }[];
  allergies: AllergyRow[];
}

export interface PatientSearchRow {
  id: string;
  display_name: string;
  date_of_birth: string | null;
  sex: string;
}

export function searchPatients(query: string, limit = 20, signal?: AbortSignal) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return api<{ patients: PatientSearchRow[]; has_more: boolean }>(`/patients/search?${params}`, { signal });
}

export interface ChartRegion {
  region_key: string;
  display_name: string;
  mesh_name: string;
  specialties: string[];
}

export interface ChartCondition {
  id: string;
  name: string;
  status: string;
  onset_date: string | null;
  body_region_key: string;
}

export interface ChartMedication {
  id: string;
  name: string;
  dose: string;
  route: string;
  frequency: string;
  status: string;
  start_date: string | null;
  body_region_key: string;
}

export interface ChartSeries {
  name: string;
  unit: string;
  body_region_key: string;
  points: { id: string; at: string; value: number; source: string; document_id: string | null }[];
}

export interface ChartEncounter {
  id: string;
  encounter_type: string;
  occurred_at: string;
  summary: string;
}

export interface ChartNoteRow {
  id: string;
  body: string;
  created_at: string;
  source_suggestion_id: string | null;
}

export interface ChartReminder {
  id: string;
  name: string;
  due_on: string;
  status: string;
  rule: { name: string; baseline_age: number; guideline_source_id: string } | null;
}

export interface ChartAppointment {
  id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  status: string;
}

export interface ChartCoverage {
  payer_name: string;
  plan_name: string;
  active: boolean;
  copay: number;
  deductible_remaining: number;
}

export interface PatientChart {
  patient: ChartPatient;
  regions: ChartRegion[];
  conditions: ChartCondition[];
  medications: ChartMedication[];
  series: ChartSeries[];
  encounters: ChartEncounter[];
  notes: ChartNoteRow[];
  reminders: ChartReminder[];
  appointments: ChartAppointment[];
  coverage: ChartCoverage | null;
  pending_suggestions: number;
}

export interface BodyRegionState {
  region_key: string;
  mesh_name: string;
  emphasis: "focus" | "dim";
  pulse: boolean;
  condition_count: number;
}

export interface TimelineEvent {
  at: string;
  kind: string;
  label: string;
}

export interface BodyState {
  patient: { id: string; display_name: string; age: number };
  specialty: string;
  regions: BodyRegionState[];
  timeline: TimelineEvent[];
  trends: { name: string; unit: string; points: { at: string; value: number }[] }[];
}

export interface RegionChart {
  region_key: string;
  conditions: { name: string; status: string; onset_date?: string }[];
  medications: { name: string; dose: string; route: string; frequency: string; status: string }[];
  observations: { name: string; value: number; unit: string; observed_at?: string }[];
}

export interface ReminderRow {
  id: string;
  patient_id: string;
  name: string;
  due_on: string;
  status: string;
}

export interface CitationRow {
  source_id?: string;
  title?: string;
  passage?: string;
  tier?: string;
}

export interface SuggestionRow {
  id: string;
  patient_id: string;
  kind: string;
  status: "pending" | "approved" | "rejected";
  target_table: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  reason: string;
  confidence: number;
  citations: CitationRow[];
  source: string;
}

export interface DoctorRequest {
  request_id: string;
  transcript: string;
  route: "chart_update" | "clinical_question" | "check_screenings";
  suggestions: SuggestionRow[];
  answer: { text: string; citations: CitationRow[] } | null;
  spoken_text: string | null;
  audio_base64: string | null;
}

export interface DocumentResult {
  document_id: string;
  analytes: { name: string; value: number; unit: string; flag?: string }[];
  suggestions: SuggestionRow[];
}

export interface ReminderRun {
  sent: { reminder_id: string; sms_id: string }[];
  skipped: { reminder_id: string; reason: string }[];
}

function messageFrom(body: unknown, statusText: string): string {
  if (body && typeof body === "object") {
    const record = body as { error?: { message?: string }; detail?: unknown };
    if (record.error?.message) return record.error.message;
    if (typeof record.detail === "string") return record.detail;
  }
  return statusText || "The clinic API rejected the request.";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { ...init, cache: "no-store" });
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) throw new ApiError(messageFrom(body, response.statusText), response.status);
  return body as T;
}

export function listPatients() {
  return api<{ patients: ChartPatient[] }>("/patients");
}

export function getChart(patientId: string) {
  return api<PatientChart>(`/patients/${patientId}/chart`);
}

export function getBodyState(patientId: string, specialty: string) {
  const query = new URLSearchParams({ specialty });
  return api<BodyState>(`/patients/${patientId}/body-state?${query}`);
}

export function getRegion(patientId: string, regionKey: string) {
  return api<RegionChart>(`/patients/${patientId}/regions/${regionKey}`);
}

export function listReminders(patientId: string) {
  return api<{ reminders: ReminderRow[] }>(`/patients/${patientId}/reminders`);
}

export async function listSuggestions(patientId: string) {
  const statuses = ["pending", "approved", "rejected"] as const;
  const pages = await Promise.all(
    statuses.map((status) => {
      const query = new URLSearchParams({ patient_id: patientId, status });
      return api<{ suggestions: SuggestionRow[] }>(`/suggestions?${query}`);
    }),
  );
  return pages.flatMap((page) => page.suggestions);
}

export function postRequest(patientId: string, text: string) {
  const body = new FormData();
  body.set("patient_id", patientId);
  body.set("text", text);
  return api<DoctorRequest>("/requests", { method: "POST", body });
}

export function postVoiceRequest(patientId: string, audio: Blob) {
  const body = new FormData();
  body.set("patient_id", patientId);
  body.set("audio", audio, "dictation.webm");
  return api<DoctorRequest>("/requests", { method: "POST", body });
}

export interface EligibilityResult {
  coverage: { payer_name: string; member_id: string; plan_name: string; active: boolean; deductible_remaining: number; copay: number; benefits: { name: string; detail: string }[] };
  summary: string;
  prior_auth: { note: string; citations: CitationRow[] } | null;
}

export function checkEligibility(patientId: string, orderText: string) {
  return api<EligibilityResult>(`/patients/${patientId}/eligibility`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_text: orderText || null }),
  });
}

export function approveSuggestions(suggestionIds: string[]) {
  return api<{ approved: SuggestionRow[]; reminder_review: { suggestions: SuggestionRow[]; answer: string | null } }>(
    "/suggestions/approve",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestion_ids: suggestionIds }),
    },
  );
}

export function rejectSuggestions(suggestionIds: string[], reason: string) {
  return api<{ rejected: SuggestionRow[] }>("/suggestions/reject", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ suggestion_ids: suggestionIds, reason }),
  });
}

export function uploadDocument(patientId: string, file: File) {
  const body = new FormData();
  body.set("patient_id", patientId);
  body.set("file", file);
  return api<DocumentResult>("/documents", { method: "POST", body });
}

export function runReminderJob(asOf: string) {
  return api<ReminderRun>("/demo/run-reminders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ as_of: asOf }),
  });
}

export function sendStop(phoneE164: string) {
  const body = new URLSearchParams();
  body.set("MessageSid", `SM${crypto.randomUUID().replaceAll("-", "")}`);
  body.set("MessageStatus", "received");
  body.set("From", `whatsapp:${phoneE164}`);
  body.set("Body", "STOP");
  return api<null>("/webhooks/twilio", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
}
