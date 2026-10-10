"use client";

import { cloneElement, isValidElement, useId, useState, type FormEvent, type ReactNode } from "react";
import { create } from "zustand";
import { ApiError, saveChartEntry } from "@/lib/api";
import { useStore } from "@/lib/store";
import { formatDate } from "@/lib/data";

export const entryButton = "rounded-md border border-hairline-strong bg-white px-3 py-2 text-[13px] font-medium text-jade-700 hover:bg-jade-50 disabled:opacity-50";
export const entryInput = "mt-1.5 w-full min-w-0 rounded-md border border-hairline-strong bg-white px-3 py-2 text-[14px] text-ink focus:outline-2 focus:outline-jade-600";
export const localDate = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

// Keep unsaved capture in memory when switching tabs; never put patient data in localStorage.
interface Capture { values: Record<string, string>; submissionId?: string; pending: boolean; message: string; error: boolean; saved: boolean; uncertain?: boolean }
const useCapture = create<{ drafts: Record<string, Capture>; put: (key: string, draft: Capture) => void; remove: (key: string) => void }>((set) => ({
  drafts: {}, put: (key, draft) => set((s) => ({ drafts: { ...s.drafts, [key]: draft } })),
  remove: (key) => set((state) => { const drafts = { ...state.drafts }; delete drafts[key]; return { drafts }; }),
}));

export function startChartEntry(patientId: string, path: string) {
  const capture = useCapture.getState();
  const key = `${patientId}:${path}`;
  if (capture.drafts[key]?.saved) capture.remove(key);
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return <div className="min-w-0"><label htmlFor={id} className="block text-[13px] font-medium text-ink-soft">{label}</label>{isValidElement<{ id?: string }>(children) ? cloneElement(children, { id }) : children}</div>;
}

export function EntryForm({ patientId, title, path, initial, children, build, method = "POST", onSaved, formKey, defaultOpen = false }: {
  patientId: string; title: string; path: string; initial: Record<string, string>;
  children: (values: Record<string, string>, change: (key: string, value: string) => void) => ReactNode;
  build: (values: Record<string, string>) => Record<string, unknown>; method?: string; onSaved?: () => void; formKey?: string; defaultOpen?: boolean;
}) {
  const patient = useStore((s) => s.patients[patientId]);
  const refresh = useStore((s) => s.refreshPatient);
  const key = `${patientId}:${formKey ?? path}`;
  const stored = useCapture((s) => s.drafts[key]);
  const put = useCapture((s) => s.put);
  const draft = stored ?? { values: initial, pending: false, message: "", error: false, saved: false };
  const [open, setOpen] = useState(defaultOpen || Boolean(stored && !stored.saved));
  const id = useId();
  if (!patient) return null;
  const change = (field: string, value: string) => put(key, { ...draft, values: { ...draft.values, [field]: value }, submissionId: undefined, message: "", saved: false, error: false });
  const refreshSaved = async () => {
    try {
      await refresh(patientId);
      put(key, { ...draft, saved: true, pending: false, error: false, message: "Saved to the chart." });
      onSaved?.();
    } catch {
      put(key, { ...draft, saved: true, pending: false, error: true, message: "Saved to the backend. The chart could not refresh; retry the refresh below." });
    }
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (draft.pending || draft.saved) return;
    const submissionId = draft.submissionId ?? crypto.randomUUID();
    const submitted = { ...draft, submissionId, pending: true, message: "", error: false };
    put(key, submitted);
    try {
      await saveChartEntry(patientId, path, build(draft.values), submissionId, method);
    } catch (error) {
      put(key, { ...submitted, pending: false, error: true, uncertain: !(error instanceof ApiError) || error.status >= 500, message: error instanceof ApiError ? error.message : "Save could not be confirmed. Retry the same entry to check without duplicating it." });
      return;
    }
    put(key, { ...submitted, pending: false, saved: true, message: "Saved to the chart." });
    try { await refresh(patientId); onSaved?.(); setOpen(false); }
    catch { put(key, { ...submitted, pending: false, saved: true, error: true, message: "Saved to the backend. The chart could not refresh; retry the refresh below." }); }
  };
  return <section className={open ? "mt-5 rounded-lg border border-hairline bg-ivory/60 p-5" : "mt-5"}>
    <div className={`flex flex-wrap items-center gap-3 ${open ? "justify-between" : "justify-end"}`}>
      {open && <div className="min-w-0"><h2 className="font-sans text-[14px] font-semibold">{title}</h2><p className="mt-1 text-[12px] text-ink-soft">{patient.name} · DOB {formatDate(patient.dob) || "not recorded"} · {patient.mrn}</p></div>}
      <button className={entryButton} type="button" aria-expanded={open} aria-controls={id} disabled={draft.pending} onClick={() => {
        if (!open && draft.saved) put(key, { values: initial, pending: false, message: "", error: false, saved: false });
        setOpen(!open);
      }}>{open ? "Collapse form" : title}</button>
    </div>
    {open && <form id={id} onSubmit={submit} className="mt-5">
      <fieldset disabled={draft.pending || draft.saved || draft.uncertain} className="grid min-w-0 gap-x-6 gap-y-5 @min-[700px]:grid-cols-2">{children(draft.values, change)}</fieldset>
      <div className="mt-5 flex flex-wrap items-center gap-3"><button type="submit" disabled={draft.pending || draft.saved} className="rounded-md bg-jade-900 px-4 py-2 text-[13px] font-medium text-white disabled:opacity-50">{draft.pending ? "Saving…" : "Save to chart"}</button><button type="button" className={entryButton} disabled={draft.pending || draft.saved || draft.uncertain} title="Reset unsaved values to this form's starting values" onClick={() => put(key, { values: initial, pending: false, message: "", error: false, saved: false })}>Reset form</button><p className="text-[12px] text-ink-faint">{method === "PUT" ? "Updates the recorded entry; previous values remain in the audit history." : "Adds a recorded chart entry."}</p></div>
    </form>}
    {draft.message && <p role={draft.error ? "alert" : "status"} className={`mt-3 text-[13px] ${draft.error ? "text-critical" : "text-jade-700"}`}>{draft.message}</p>}
    {draft.saved && draft.error && <button className={`${entryButton} mt-3`} type="button" onClick={refreshSaved}>Refresh saved chart</button>}
  </section>;
}

export function VitalsEntry({ patientId }: { patientId: string }) {
  return <EntryForm patientId={patientId} title="Record vitals" path="vitals" initial={{ observed_at: localDate(), systolic: "", diastolic: "", weight_kg: "", pulse: "" }} build={(v) => ({
    observed_at: new Date(v.observed_at).toISOString(),
    ...Object.fromEntries(["systolic", "diastolic", "weight_kg", "pulse"].map((k) => [k, v[k] === "" ? null : Number(v[k])])),
  })}>{(v, change) => <>
    <Field label="Measured at (local time)"><input className={entryInput} type="datetime-local" required value={v.observed_at} onChange={(e) => change("observed_at", e.target.value)} /></Field>
    <p className="self-end text-[12px] leading-relaxed text-ink-soft">Enter any measured values. Blood pressure requires both numbers. Blank fields remain unrecorded.</p>
    {[ ["systolic", "Systolic BP (mmHg)"], ["diastolic", "Diastolic BP (mmHg)"], ["weight_kg", "Weight (kg)"], ["pulse", "Pulse (beats/min)"] ].map(([key, label]) => <Field key={key} label={label}><input className={entryInput} type="number" min="0.01" step="any" value={v[key]} onChange={(e) => change(key, e.target.value)} /></Field>)}
  </>}</EntryForm>;
}
