const ROUTE_LABELS: Record<string, string> = {
  chart_update: "Chart update",
  clinical_question: "Clinical question",
  check_screenings: "Screening review",
};

const KIND_LABELS: Record<string, string> = {
  field_update: "Chart field",
  reminder_change: "Reminder",
  soap_note: "SOAP note",
  observation: "Observation",
  plan_item: "Plan item",
};

const FLAG_LABELS: Record<string, string> = {
  out_of_range: "Out of range",
  low_confidence: "Low confidence",
};

export function routeLabel(route: string): string {
  return ROUTE_LABELS[route] ?? route;
}

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function flagLabel(flag: string): string {
  return FLAG_LABELS[flag] ?? flag;
}

export function isOpenableLocator(locator: string): boolean {
  return /^https?:\/\//i.test(locator);
}

export function displayValue(value: unknown): string {
  if (value == null || value === "") return "empty";
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }
  return JSON.stringify(value);
}

export function diffLines(
  before: Record<string, unknown> | null | undefined,
  after: Record<string, unknown> | null | undefined,
): string[] {
  const left = before ?? {};
  const right = after ?? {};
  const keys = [...new Set([...Object.keys(left), ...Object.keys(right)])];
  return keys.map((key) => {
    const hasLeft = Object.prototype.hasOwnProperty.call(left, key);
    const hasRight = Object.prototype.hasOwnProperty.call(right, key);
    if (hasLeft && hasRight && JSON.stringify(left[key]) !== JSON.stringify(right[key])) {
      return `${key}: ${displayValue(left[key])} → ${displayValue(right[key])}`;
    }
    if (hasRight) return `${key}: ${displayValue(right[key])}`;
    return `${key}: ${displayValue(left[key])}`;
  });
}

export function confidenceLabel(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "";
  return `${Math.round(value * 100)}% confidence`;
}

export function reviewSummary(answer: string | null, suggestionCount: number): string {
  const parts: string[] = [];
  if (answer && answer.trim()) parts.push(answer.trim());
  if (suggestionCount === 1) parts.push("1 reminder change is waiting.");
  if (suggestionCount > 1) parts.push(`${suggestionCount} reminder changes are waiting.`);
  return parts.join(" ");
}
