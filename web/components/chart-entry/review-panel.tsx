"use client";

import { useEffect, useState } from "react";
import { getEntryState, type EntryState } from "@/lib/api";
import { useStore } from "@/lib/store";
import { EntryForm, Field, entryInput } from "./entry-form";

export function ReviewPanel({ patientId, kind }: { patientId: string; kind: "medications" | "allergies" }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [state, setState] = useState<EntryState | null>(null);
  const [error, setError] = useState("");
  const records = patient?.[kind];
  useEffect(() => {
    let cancelled = false;
    getEntryState(patientId).then((data) => { if (!cancelled) { setState(data); setError(""); } })
      .catch(() => { if (!cancelled) setError("Review history could not load. Refresh this tab to try again."); });
    return () => { cancelled = true; };
  }, [patientId, records]);
  if (!patient) return null;
  const review = state?.[kind];
  const initial: Record<string, string> = { note: "", confirmed: "", expected_version: state?.versions[kind] ?? "", record_ids: JSON.stringify(records?.map((r) => r.id) ?? []), ...Object.fromEntries(patient.medications.map((m) => [`use_${m.id}`, "unknown"])) };
  return <section className="mt-6 border-t border-hairline pt-4">
    <h2 className="font-sans text-[14px] font-semibold">{kind === "medications" ? "Medication reconciliation" : "Allergy review"}</h2>
    {error ? <p role="alert" className="mt-2 text-[13px] text-critical">{error}</p> : <p className="mt-2 text-[13px] text-ink-soft">{!state ? "Loading review history…" : review ? `Last recorded review: ${new Date(review.saved_at).toLocaleString()}${review.stale ? ". Chart records have changed since this review." : "."}` : "No patient review recorded."}</p>}
    {review?.note && <p className="mt-2 whitespace-pre-wrap text-[13px] text-ink-soft">Review note: {review.note}</p>}
    {kind === "medications" && review && <ul className="mt-2 space-y-1 text-[12px] text-ink-soft">{patient.medications.filter((m) => review.medication_use[m.id]).map((m) => <li key={m.id}>{m.name}: patient-reported use {review.medication_use[m.id].replaceAll("_", " ")}{review.stale ? " (prior review)" : ""}</li>)}</ul>}
    {state && records && records.length > 0 ? <EntryForm patientId={patientId} title={kind === "medications" ? "Record medication review" : "Record allergy review"} path="chart-review" formKey={`chart-review-${kind}`} initial={initial} build={(v) => ({
      kind, record_ids: JSON.parse(v.record_ids), expected_version: v.expected_version, confirmed_with_patient: v.confirmed === "yes", note: v.note,
      medication_use: kind === "medications" ? Object.fromEntries(patient.medications.map((m) => [m.id, v[`use_${m.id}`]])) : {},
    })}>{(v, change) => <>
      {kind === "medications" && patient.medications.map((m) => <Field key={m.id} label={`${m.name} ${m.dose} · chart status ${m.status}`}><select className={entryInput} value={v[`use_${m.id}`] ?? "unknown"} onChange={(e) => change(`use_${m.id}`, e.target.value)}><option value="unknown">Use not established</option><option value="taking">Patient reports taking</option><option value="not_taking">Patient reports not taking</option></select></Field>)}
      <Field label="Review note (optional)"><textarea className={entryInput} rows={3} maxLength={2000} value={v.note} onChange={(e) => change("note", e.target.value)} /></Field>
      <label className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-soft @min-[700px]:col-span-2"><input className="mt-1 size-4 shrink-0 accent-jade-600" type="checkbox" required checked={v.confirmed === "yes"} onChange={(e) => change("confirmed", e.target.checked ? "yes" : "")} />I reviewed these records with the patient or caregiver. {kind === "medications" ? "Reported use does not change medication orders." : "This review does not replace documenting missing allergy records."}</label>
    </>}</EntryForm> : state && !records?.length ? <p className="mt-3 text-[12px] text-ink-faint">Document explicit records before recording a review. An empty list is not a verified negative history.</p> : null}
  </section>;
}
