"use client";

import { useEffect, useState } from "react";
import { getEntryState, type VisitDraftData } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Page, PageHeader } from "@/components/system/primitives";
import { EntryForm, Field, entryInput, localDate } from "@/components/chart-entry/entry-form";

export function VisitTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [draft, setDraft] = useState<VisitDraftData | null | undefined>(undefined);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    getEntryState(patientId).then((s) => { if (!cancelled) setDraft(s.draft); }).catch(() => { if (!cancelled) setError("The saved draft could not load. Refresh before editing."); });
    return () => { cancelled = true; };
  }, [patientId]);
  if (!patient) return null;
  return <Page wide>
    <PageHeader eyebrow={patient.name} title="Visit draft">Reason for visit, assessment and plan. Saved as an unsigned draft.</PageHeader>
    {error ? <p className="mt-5 text-critical" role="alert">{error}</p> : draft === undefined ? <p className="mt-5 text-ink-soft">Loading saved draft…</p> : <>
      <p className="mt-5 text-[13px] text-ink-soft">{draft?.saved_at ? `Unsigned draft · last saved ${new Date(draft.saved_at).toLocaleString()}` : "No visit draft saved for this patient."}</p>
      <EntryForm patientId={patientId} title={draft ? "Edit visit draft" : "Start visit draft"} path="visit-draft" initial={{ visit_date: draft?.visit_date ?? localDate().slice(0, 10), reason: draft?.reason ?? "", assessment: draft?.assessment ?? "", plan: draft?.plan ?? "" }} build={(v) => v} onSaved={() => { void getEntryState(patientId).then((s) => setDraft(s.draft)).catch(() => setError("Saved, but the draft summary could not refresh. Reload this tab.")); }}>{(v, change) => <>
        <Field label="Visit date"><input className={entryInput} type="date" required value={v.visit_date} onChange={(e) => change("visit_date", e.target.value)} /></Field>
        <Field label="Reason for visit"><textarea className={entryInput} rows={2} required maxLength={2000} value={v.reason} onChange={(e) => change("reason", e.target.value)} /></Field>
        <Field label="Assessment"><textarea className={entryInput} rows={8} maxLength={12000} value={v.assessment} onChange={(e) => change("assessment", e.target.value)} /></Field>
        <Field label="Plan"><textarea className={entryInput} rows={8} maxLength={12000} value={v.plan} onChange={(e) => change("plan", e.target.value)} /></Field>
      </>}</EntryForm>
      {draft && <section className="mt-7 space-y-5 border-t border-hairline pt-5"><h2 className="font-sans text-[15px] font-semibold">Saved draft · {draft.visit_date}</h2>{[["Reason for visit", draft.reason], ["Assessment", draft.assessment], ["Plan", draft.plan]].map(([title, text]) => <div key={title}><h3 className="text-[13px] font-semibold">{title}</h3><p className="mt-2 whitespace-pre-wrap text-[14px] leading-relaxed text-ink-soft">{text || "Not yet drafted."}</p></div>)}</section>}
    </>}
  </Page>;
}
