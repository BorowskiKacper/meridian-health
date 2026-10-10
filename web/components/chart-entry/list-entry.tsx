"use client";

import { EntryForm, Field, entryInput, localDate } from "./entry-form";
import { useStore } from "@/lib/store";
import type { Allergy, Medication } from "@/lib/types";

export function ListEntry({ patientId, kind, record, onSaved }: { patientId: string; kind: "problems" | "medications" | "allergies"; record?: Medication | Allergy; onSaved?: () => void }) {
  const patient = useStore((s) => s.patients[patientId]);
  if (!patient) return null;
  const medication = kind === "medications" ? record as Medication | undefined : undefined;
  const allergy = kind === "allergies" ? record as Allergy | undefined : undefined;
  const initial: Record<string, string> = kind === "medications" ? {
    name: medication?.name ?? "", dose: medication?.dose ?? "", route: medication?.route ?? "", frequency: medication?.frequency ?? "",
    status: medication?.status ?? "active", start_date: medication?.start ?? "", body_region_key: medication?.regionKey ?? "",
  } : kind === "allergies" ? {
    substance: allergy?.substance ?? "", category: allergy?.category ?? "drug", reaction: allergy?.reaction ?? "", severity: allergy?.severity ?? "unknown", status: allergy?.status ?? "active", recorded_on: allergy?.recordedOn ?? localDate().slice(0, 10),
  } : { name: "", status: "active", onset_date: "", body_region_key: "" };
  const label = kind === "medications" ? "medication record" : kind === "allergies" ? "allergy record" : "problem";
  return <EntryForm key={`${patientId}-${kind}-${record?.id ?? "new"}`} patientId={patientId} title={`${record ? "Edit" : "Add"} ${label}`} path={`${kind}${record ? `/${record.id}` : ""}`} method={record ? "PUT" : "POST"} initial={initial} build={(v) => v} onSaved={onSaved} defaultOpen={Boolean(record)}>
    {(v, change) => <>
      <p className="text-[12px] leading-relaxed text-ink-soft @min-[700px]:col-span-2">{kind === "medications" ? "Document a medication in the patient's history. This does not issue a prescription or change a treatment order." : kind === "allergies" ? "Record the reported substance and reaction. A clinician review is a separate action below." : "Document an established problem and its recorded onset date."}</p>
      {Object.keys(initial).map((key) => {
        const labels: Record<string, string> = { name: kind === "medications" ? "Medication name" : "Problem name", dose: "Dose", route: "Route", frequency: "Frequency", status: "Recorded status", start_date: "Started on", onset_date: "Onset date", body_region_key: "Related chart region", substance: "Allergen / substance", category: "Category", reaction: "Reported reaction", severity: "Recorded severity", recorded_on: "Recorded on" };
        const options = key === "status" ? ["active", kind === "medications" ? "stopped" : kind === "allergies" ? "inactive" : "resolved"] : key === "category" ? ["drug", "food", "environmental"] : key === "severity" ? ["unknown", "mild", "moderate", "severe", "anaphylaxis"] : null;
        if (key === "body_region_key") return <Field key={key} label={labels[key]}><select className={entryInput} required value={v[key]} onChange={(e) => change(key, e.target.value)}><option value="" disabled>Choose a chart region</option>{patient.chartRegions.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select></Field>;
        return <Field key={key} label={labels[key]}>{options ? <select className={entryInput} value={v[key]} onChange={(e) => change(key, e.target.value)}>{options.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}</select> : <input className={entryInput} type={key.endsWith("date") || key === "recorded_on" ? "date" : "text"} maxLength={key === "reaction" ? 500 : key === "route" ? 100 : 200} required value={v[key]} onChange={(e) => change(key, e.target.value)} />}</Field>;
      })}
    </>}
  </EntryForm>;
}
