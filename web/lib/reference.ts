/**
 * Reference ranges for the analytes the practice charts most.
 *
 * These are adult primary care defaults for display only. A lab's printed range
 * wins when a document carries one, and the plan is to move these into a
 * terminology table with LOINC codes once lab extraction stores them.
 */
export interface ReferenceRange {
  low?: number;
  high?: number;
  /** Short note on what the band means, e.g. a treatment goal rather than a population range. */
  label: string;
  /** Which direction is the worrying one when a value leaves the band. */
  worse: "high" | "low" | "either";
}

const RANGES: Record<string, ReferenceRange> = {
  A1c: { high: 7, label: "Goal below 7% for most adults with diabetes", worse: "high" },
  LDL: { high: 100, label: "Goal below 100 mg/dL; below 70 with ASCVD", worse: "high" },
  "Systolic blood pressure": { low: 90, high: 130, label: "Goal below 130/80 with diabetes or CKD", worse: "either" },
  "Diastolic blood pressure": { low: 60, high: 80, label: "Goal below 130/80 with diabetes or CKD", worse: "either" },
  eGFR: { low: 60, label: "Below 60 for three months defines CKD stage 3", worse: "low" },
  Creatinine: { low: 0.6, high: 1.1, label: "Adult reference range", worse: "high" },
  "Urine albumin-creatinine ratio": { high: 30, label: "30 mg/g or more is albuminuria", worse: "high" },
  Hemoglobin: { low: 12, high: 16, label: "Adult female reference range", worse: "low" },
  Ferritin: { low: 12, high: 150, label: "Adult reference range", worse: "low" },
  SpO2: { low: 95, label: "Resting room air", worse: "low" },
  "FEV1 percent predicted": { low: 80, label: "Below 80% predicted is airflow limitation", worse: "low" },
  TSH: { low: 0.4, high: 4, label: "Adult reference range", worse: "either" },
  Glucose: { low: 70, high: 99, label: "Fasting", worse: "high" },
  ALT: { low: 7, high: 56, label: "Adult reference range", worse: "high" },
};

export function referenceFor(analyte: string): ReferenceRange | undefined {
  return RANGES[analyte];
}

export type Flag = "high" | "low" | null;

export function flagValue(analyte: string, value: number): Flag {
  const range = RANGES[analyte];
  if (!range) return null;
  if (range.high !== undefined && value > range.high) return "high";
  if (range.low !== undefined && value < range.low) return "low";
  return null;
}

/** Whether a flagged value is in the direction the clinician worries about. */
export function isConcerning(analyte: string, value: number): boolean {
  const flag = flagValue(analyte, value);
  const range = RANGES[analyte];
  if (!flag || !range) return false;
  return range.worse === "either" || range.worse === flag;
}
