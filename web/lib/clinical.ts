import type { Allergy, Trend } from "./types";

export function recordedPoints(trend: Trend) {
  return trend.points.filter((p) => Number.isFinite(p.value) && Number.isFinite(Date.parse(p.at)))
    .sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
}

export function sourceLabel(source?: string) {
  if (source === "manual_entry") return "Manual entry";
  if (source === "demo_vitals") return "Synthetic demo vitals";
  if (source === "seed") return "Demo seed record";
  return source?.replaceAll("_", " ") || "Source not recorded";
}

export function currentAllergies(allergies: Allergy[]) {
  return allergies.filter((a) => a.status === "active");
}

export function allergySummary(allergies: Allergy[]) {
  const active = currentAllergies(allergies);
  const recorded = active.filter((a) => a.category !== "nkda");
  if (recorded.length) return recorded.map((a) => a.substance).join(", ");
  return active.some((a) => a.category === "nkda") ? "No known drug allergies" : "Status not recorded";
}

export function isVital(trend: Trend) {
  return /blood pressure|^weight$|^body weight$|^height$|^body height$|^bmi$|^body mass index$|^pulse$|^heart rate$|^respiratory rate$|^temperature$|^body temperature$|^spo2$|oxygen saturation/i.test(trend.name);
}

export function bloodPressure(trends: Trend[]) {
  return trends.filter((t) => /^(systolic|diastolic) blood pressure$/i.test(t.name) && ["mmhg", "mm[hg]"].includes(t.unit.toLowerCase()))
    .sort((a, b) => Number(a.name.toLowerCase().startsWith("diastolic")) - Number(b.name.toLowerCase().startsWith("diastolic")));
}

export function weightTrend(trends: Trend[]) {
  return trends.find((t) => /^(body )?weight$/i.test(t.name));
}
