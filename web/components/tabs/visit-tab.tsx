"use client";

import { useEffect, useState } from "react";
import { getEntryState, type VisitDraftData } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Page, PageHeader } from "@/components/system/primitives";
import { EntryForm, Field, entryInput, localDate, startChartEntry } from "@/components/chart-entry/entry-form";
import { MeasurementList } from "@/components/charts/measurement-list";
import { isVital } from "@/lib/clinical";

export function VisitTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [draft, setDraft] = useState<VisitDraftData | null | undefined>(undefined);
  const [unsaved, setUnsaved] = useState(false);
  const [error, setError] = useState("");
  const openTab = useStore((s) => s.openTab);
  useEffect(() => {
    let cancelled = false;
    getEntryState(patientId).then((s) => { if (!cancelled) setDraft(s.draft); }).catch(() => { if (!cancelled) setError("The saved draft could not load. Refresh before editing."); });
    return () => { cancelled = true; };
  }, [patientId]);
  if (!patient) return null;
  return <Page wide>
    <PageHeader eyebrow={draft?.finalized_at ? "Visit · finalized" : "Visit · unsigned"} title={draft?.finalized_at ? "Finalized visit note" : "Visit draft"}>Capture the visit while keeping the recorded chart and proposed changes separate.</PageHeader>
    <details className="mt-6 rounded-lg border border-hairline bg-ivory p-4"><summary className="cursor-pointer text-[13px] font-semibold text-jade-700">Chart context for this visit</summary><div className="mt-4 grid gap-6 @min-[700px]:grid-cols-2"><div><button type="button" className="text-[13px] font-medium text-jade-700 hover:underline" onClick={() => openTab("problems", patientId)}>Current problem list →</button><p className="mt-2 text-[13px] leading-relaxed text-ink-soft">{patient.problems.filter((p) => p.status !== "resolved").map((p) => p.name).join(" · ") || "No active problems recorded."}</p></div><div><button type="button" className="text-[13px] font-medium text-jade-700 hover:underline" onClick={() => openTab("medications", patientId)}>Review medications →</button><p className="mt-2 text-[13px] leading-relaxed text-ink-soft">{patient.medications.filter((m) => m.status === "active").map((m) => `${m.name} ${m.dose} ${m.frequency}`).join(" · ") || "No active medications recorded."}</p></div></div><p className="mt-5 mb-3 text-[12px] text-ink-faint">Latest recorded vitals · verify collection dates before using them for today’s visit.</p><MeasurementList series={patient.trends.filter(isVital)} /><button type="button" className="mt-3 text-[13px] text-jade-700 hover:underline" onClick={() => openTab("vitals", patientId)}>Record today’s vitals →</button></details>
    {error ? <p className="mt-5 text-critical" role="alert">{error}</p> : draft === undefined ? <p className="mt-5 text-ink-soft">Loading saved draft…</p> : <>
      <p className="mt-5 text-[13px] text-ink-soft">{draft?.finalized_at ? `Finalized ${new Date(draft.finalized_at).toLocaleString()} by ${draft.finalized_by}` : draft?.saved_at ? `Unsigned draft · last saved ${new Date(draft.saved_at).toLocaleString()}` : "No visit draft saved for this patient."}</p>
      {!draft?.finalized_at && <EntryForm patientId={patientId} onEdited={() => setUnsaved(true)} title={draft ? "Edit visit draft" : "Start visit draft"} path="visit-draft" defaultOpen saveLabel="Save unsigned draft" saveHint="Saves a draft; does not sign the encounter or submit orders." initial={{ visit_date: draft?.visit_date ?? localDate().slice(0, 10), reason: draft?.reason ?? "", assessment: draft?.assessment ?? "", plan: draft?.plan ?? "" }} build={(v) => v} onSaved={() => { setUnsaved(false); void getEntryState(patientId).then((s) => setDraft(s.draft)).catch(() => setError("Saved, but the draft summary could not refresh. Reload this tab.")); }}>{(v, change) => <>
        <Field label="Visit date"><input className={entryInput} type="date" required value={v.visit_date} onChange={(e) => change("visit_date", e.target.value)} /></Field>
        <div className="@min-[700px]:col-span-2"><Field label="Reason for visit / history"><textarea className={entryInput} rows={3} required maxLength={2000} value={v.reason} onChange={(e) => change("reason", e.target.value)} /></Field></div>
        <div className="@min-[700px]:col-span-2"><Field label="Assessment"><textarea className={entryInput} rows={5} maxLength={12000} value={v.assessment} onChange={(e) => change("assessment", e.target.value)} /></Field></div>
        <div className="@min-[700px]:col-span-2"><Field label="Plan"><textarea className={entryInput} rows={5} maxLength={12000} value={v.plan} onChange={(e) => change("plan", e.target.value)} /></Field></div>
      </>}</EntryForm>}
      {draft && <details className="mt-7 border-t border-hairline pt-5"><summary className="cursor-pointer text-[13px] font-semibold text-jade-700">{draft.finalized_at ? "Finalized note" : "Saved draft"} · {draft.visit_date}</summary><div className="mt-4 space-y-5">{[["Reason for visit", draft.reason], ["Assessment", draft.assessment], ["Plan", draft.plan]].map(([title, text]) => <div key={title}><h3 className="text-[13px] font-semibold">{title}</h3><p className="mt-2 whitespace-pre-wrap text-[14px] leading-relaxed text-ink-soft">{text || "Not yet drafted."}</p></div>)}</div></details>}
      {draft && !draft.finalized_at && !unsaved && draft.draft_id && <EntryForm key={draft.draft_id} patientId={patientId} path="visit-draft/finalize" formKey={`finalize-${draft.draft_id}`} title="Review saved visit note" saveLabel="Finalize visit note" saveHint="Adds this saved note to Timeline. Does not submit prescriptions or orders." initial={{ finalized_by: "" }} build={(v) => ({ draft_id: draft.draft_id, finalized_by: v.finalized_by, confirmed_review: true })} onSaved={() => { void getEntryState(patientId).then((s) => setDraft(s.draft)).catch(() => setError("Finalized, but the summary could not refresh. Reload this tab.")); }}>{(v, change) => <>
        <div className="@min-[700px]:col-span-2 rounded-md border border-hairline bg-clinical-surface p-4"><p className="text-[13px] font-semibold">Visit date: {draft.visit_date}</p>{[["Reason for visit / history", draft.reason], ["Assessment", draft.assessment], ["Plan", draft.plan]].map(([title, text]) => <div key={title} className="mt-4"><h3 className="text-[13px] font-semibold">{title}</h3><p className="mt-1 whitespace-pre-wrap text-[14px] text-ink-soft">{text || "Not recorded"}</p></div>)}</div>
        <Field label="Finalized by"><input className={entryInput} required maxLength={120} value={v.finalized_by} onChange={(e) => change("finalized_by", e.target.value)} autoComplete="name" /></Field>
        <p className="text-[12px] text-ink-soft">Name is self-reported; clinician identity is not authenticated.</p>
        <label className="flex items-start gap-2 text-[13px] @min-[700px]:col-span-2"><input type="checkbox" required className="mt-1 accent-jade-600" />I reviewed this saved note and confirm it is ready for the patient&apos;s historical record.</label>
      </>}</EntryForm>}
      {unsaved && !draft?.finalized_at && <p className="mt-4 text-[13px] text-ink-soft">Save your changes before reviewing the note for finalization.</p>}
      {draft?.finalized_at && <div className="mt-5 flex gap-3"><button type="button" className="rounded-md bg-jade-700 px-3 py-2 text-[13px] text-white hover:bg-jade-800" onClick={() => openTab("timeline", patientId)}>View historical notes</button><button type="button" className="rounded-md border border-hairline px-3 py-2 text-[13px] hover:bg-jade-100" onClick={() => { startChartEntry(patientId, "visit-draft"); setDraft(null); setUnsaved(false); }}>Start another visit</button></div>}
      <p className="mt-6 text-[12px] leading-relaxed text-ink-faint">Authenticated signing, structured physical-exam fields, e-prescribing, and lab or imaging order submission are not available yet. Document planned actions here; update chart lists directly or review supported assistant proposals.</p>
    </>}
  </Page>;
}
