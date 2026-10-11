import type { Finding, Patient, Specialty, TabKind } from "./types";

export const NOW_MINUTE = 100;

/** Anatomy loaded around the findings so the marks sit on a recognisable torso. */
export const bodyContext = [
  "skeletal.ribs",
  "skeletal.sternum",
  "skeletal.clavicle_l",
  "skeletal.clavicle_r",
  "visceral.lungs",
  "cardiovascular.heart",
  "visceral.liver",
  "visceral.stomach",
  "visceral.pancreas",
  "visceral.kidney_l",
  "visceral.kidney_r",
  "visceral.colon",
  "visceral.thyroid_gland",
  "lymphoid.spleen",
  "skeletal.femur_l",
  "skeletal.patella_l",
  "skeletal.tibia_l",
  "skeletal.fibula_l",
];

export const tabLabel: Record<TabKind, string> = {
  overview: "Overview",
  visit: "Visit draft",
  vitals: "Vitals",
  problems: "Problems",
  medications: "Medications",
  allergies: "Allergies",
  body: "Anatomy",
  region: "Region",
  timeline: "Timeline",
  queue: "Approvals",
  research: "Research",
  lab: "Diagnostics",
  history: "History & coverage",
  reminders: "Follow-up",
};

export const openableTabs: TabKind[] = ["overview", "visit", "vitals", "problems", "medications", "allergies", "lab", "history", "timeline", "body", "queue", "reminders"];

const SPECIALTY_NAMES: Record<string, string> = {
  all: "All findings",
  primary_care: "Primary care",
  cardiology: "Cardiology",
  gastroenterology: "Gastroenterology",
  pulmonology: "Pulmonology",
  endocrinology: "Endocrinology",
  nephrology: "Nephrology",
  trauma: "Trauma",
};

export function specialtyLabel(specialty: Specialty): string {
  if (SPECIALTY_NAMES[specialty]) return SPECIALTY_NAMES[specialty];
  const words = specialty.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const severityLabel = { critical: "Critical", watch: "Review", clear: "Recorded" } as const;
export const kindLabel = { injury: "Injury", disease: "Disease", lab: "Lab" } as const;

const MONTH_YEAR: Intl.DateTimeFormatOptions = { month: "short", year: "numeric", timeZone: "UTC" };
const FULL_DATE: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" };

export function formatMonth(iso: string | number | Date): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso) : date.toLocaleDateString("en-US", MONTH_YEAR);
}

export function formatDate(iso: string | number | Date | undefined | null): string {
  if (iso === undefined || iso === null) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso) : date.toLocaleDateString("en-US", FULL_DATE);
}

export function shownWhen(minute: number, when?: string): string {
  return when ?? (minute >= NOW_MINUTE ? "Now" : "");
}

/** The calendar instant a slider position stands for on this patient's chart. */
export function dateAtMinute(patient: Pick<Patient, "span">, minute: number): Date {
  const { start, end } = patient.span;
  if (minute >= NOW_MINUTE || end <= start) return new Date(end);
  return new Date(start + ((end - start) * minute) / NOW_MINUTE);
}

export function minuteAt(iso: string | number, span: { start: number; end: number }): number {
  const at = typeof iso === "number" ? iso : Date.parse(iso);
  if (Number.isNaN(at) || span.end <= span.start) return NOW_MINUTE;
  return Math.max(0, Math.min(NOW_MINUTE, Math.round(((at - span.start) / (span.end - span.start)) * NOW_MINUTE)));
}

export function findingVisible(finding: Finding, minute: number, specialty: Specialty): boolean {
  if (finding.minute > minute) return false;
  return specialty === "all" || finding.specialties.includes(specialty);
}

/** Subtle accents supplement the explicit patient names and initials. */
const PATIENT_HUES = ["#c4d9cb", "#dce8e1", "#b7d0c5", "#d4dfd4", "#c7dcd6", "#dfe7d9"];

export function patientHue(patientId: string): string {
  let hash = 0;
  for (const char of patientId) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return PATIENT_HUES[hash % PATIENT_HUES.length]!;
}

export const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name;

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

export const labPanel = {
  title: "Comprehensive metabolic panel",
  lab: "Riverside Clinical Labs",
  collected: "Collected this morning",
  rows: [
    { test: "ALT", value: "88", unit: "U/L", range: "7–56", flag: "High" },
    { test: "AST", value: "41", unit: "U/L", range: "10–40", flag: "High" },
    { test: "Creatinine", value: "1.3", unit: "mg/dL", range: "0.6–1.1", flag: "High" },
    { test: "Sodium", value: "139", unit: "mmol/L", range: "135–145", flag: "" },
    { test: "Potassium", value: "4.1", unit: "mmol/L", range: "3.5–5.1", flag: "" },
    { test: "Glucose", value: "104", unit: "mg/dL", range: "70–99", flag: "High" },
  ],
};
