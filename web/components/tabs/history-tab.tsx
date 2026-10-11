"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { formatDate } from "@/lib/data";
import { checkEligibility, type EligibilityResult } from "@/lib/api";
import { Page, PageHeader } from "@/components/system/primitives";
import { entryButton, entryInput } from "@/components/chart-entry/entry-form";

export function HistoryTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [order, setOrder] = useState("");
  const [result, setResult] = useState<EligibilityResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  if (!patient) return null;
  const procedures = patient.encounters.filter((e) => /procedure|surgery|operation/i.test(e.type));
  return <Page wide>
    <PageHeader eyebrow="Longitudinal record" title="History & coverage">Family history, recorded procedures, appointments, and coverage context.</PageHeader>
    <div className="mt-8 grid gap-8 @min-[700px]:grid-cols-2">
      <section><h2 className="font-sans text-[15px] font-semibold">Family history</h2><ul className="mt-4 divide-y divide-hairline border-y border-hairline">{patient.family.map((f) => <li key={f} className="py-4 text-[13px] leading-relaxed">{f}</li>)}</ul>{!patient.family.length && <p className="mt-4 text-sm text-ink-soft">No family history recorded.</p>}</section>
      <section><h2 className="font-sans text-[15px] font-semibold">Recorded procedures</h2>{procedures.length ? <ul className="mt-4 divide-y divide-hairline border-y border-hairline">{procedures.map((e) => <li key={e.id} className="py-4 text-[13px]"><time className="text-ink-faint" dateTime={e.at}>{formatDate(e.at)}</time><p className="mt-2 leading-relaxed">{e.summary}</p></li>)}</ul> : <p className="mt-4 text-sm text-ink-soft">No procedure encounters recorded. A complete surgical history is not available.</p>}</section>
    </div>
    <section className="mt-8"><h2 className="font-sans text-[15px] font-semibold">Appointments</h2><ul className="mt-4 divide-y divide-hairline border-y border-hairline">{[...patient.appointments].sort((a, b) => b.at.localeCompare(a.at)).map((a) => <li key={a.id} className="flex flex-wrap justify-between gap-3 py-4 text-[13px]"><div><p className="font-medium">{a.reason}</p><p className="mt-1 capitalize text-ink-soft">{a.status}</p></div><time className="text-right text-ink-soft" dateTime={a.at}>{new Date(a.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</time></li>)}</ul>{!patient.appointments.length && <p className="mt-4 text-sm text-ink-soft">No appointments recorded.</p>}</section>
    <section className="mt-8 border-t border-hairline pt-6"><h2 className="font-sans text-[15px] font-semibold">Coverage on record</h2>{patient.coverage ? <>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-[13px] @min-[700px]:grid-cols-4">{[["Payer / plan", `${patient.coverage.payer} · ${patient.coverage.plan}`], ["Recorded status", patient.coverage.active ? "Active" : "Inactive"], ["Recorded copay", `$${patient.coverage.copay}`], ["Deductible remaining", `$${patient.coverage.deductibleRemaining}`]].map(([label, value]) => <div key={label}><dt className="text-[12px] text-ink-faint">{label}</dt><dd className="mt-2 font-medium">{value}</dd></div>)}</dl>
      <details className="mt-6"><summary className="cursor-pointer text-[13px] font-medium text-jade-700">Review coverage for a planned service</summary><form className="mt-4" onSubmit={async (e) => { e.preventDefault(); setPending(true); setError(""); setResult(null); try { setResult(await checkEligibility(patientId, order)); } catch { setError("Coverage review could not finish. Try again later."); } finally { setPending(false); } }}><label className="text-[13px] text-ink-soft" htmlFor={`coverage-${patientId}`}>Planned service (optional)</label><input id={`coverage-${patientId}`} className={entryInput} value={order} maxLength={2000} disabled={pending} onChange={(e) => { setOrder(e.target.value); setResult(null); }} placeholder="e.g. colonoscopy" /><p className="mt-2 text-[12px] text-ink-faint">Uses recorded coverage and available payer documents. This is not a live insurer verification or a submitted order.</p><button disabled={pending} className={`${entryButton} mt-3`}>{pending ? "Reviewing…" : "Review recorded coverage"}</button></form>{error && <p role="alert" className="mt-4 text-sm text-critical">{error}</p>}{result && <div className="mt-4 space-y-3 text-[13px] leading-relaxed"><p>{result.summary}</p>{result.prior_auth && <div className="rounded-md border border-watch/25 bg-watch/5 p-4"><p className="font-semibold text-watch">Prior authorization review</p><p className="mt-2">{result.prior_auth.note}</p>{result.prior_auth.citations.map((c, i) => <p key={i} className="mt-2 text-ink-soft">{c.title || c.source_id} {c.passage}</p>)}</div>}<p className="text-[12px] text-ink-faint">A missing authorization note does not establish that authorization is unnecessary.</p></div>}</details>
    </> : <p className="mt-4 text-sm text-ink-soft">Coverage not recorded.</p>}</section>
    <details className="mt-8 border-t border-hairline pt-4 text-[13px]"><summary className="cursor-pointer font-medium text-ink-soft">Other history sources</summary><p className="mt-3 leading-relaxed text-ink-soft">Immunizations, advance directives, wearable feeds, genomic reports, and regional public-health feeds are not connected. Their absence here does not establish a negative clinical history.</p></details>
  </Page>;
}
