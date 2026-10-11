"use client";

import type { ReactNode } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { useStore } from "@/lib/store";
import { firstName, formatDate } from "@/lib/data";
import { bloodPressure, weightTrend } from "@/lib/clinical";
import { Page, PageHeader } from "@/components/system/primitives";
import { MeasurementList } from "@/components/charts/measurement-list";
import { VitalsDialog } from "@/components/chart-entry/vitals-dialog";

// Blood pressure first; the change badges and paired reading come from MeasurementList.
const VITALS = [
  { name: "Blood pressure", match: /blood pressure/i },
  { name: "Heart rate", match: /^(heart rate|pulse)$/i },
  { name: "Respiratory rate", match: /^respiratory rate$/i },
  { name: "Body temperature", match: /^(body )?temperature$/i },
];

export function OverviewTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;
  const problems = patient.problems.filter((p) => p.status !== "resolved");
  const meds = patient.medications.filter((m) => m.status === "active");
  const weight = weightTrend(patient.trends);
  const lastNote = patient.notes.filter((n) => n.kind === "note").sort((a, b) => b.at.localeCompare(a.at))[0];
  const vitals = [...bloodPressure(patient.trends), ...patient.trends.filter((t) => VITALS.slice(1).some((v) => v.match.test(t.name)))];
  return (
    <Page wide>
      <PageHeader title={`${firstName(patient.name)}’s Overview`} actions={<button type="button" className="flex h-9 items-center gap-2 rounded-md border border-hairline-strong px-3 text-[13px] text-jade-700 hover:bg-jade-50" onClick={() => openTab("body", patientId)}>3D view <ArrowUpRight className="size-3.5" /></button>} />
      <OverviewSection className="mt-6" title="Last visit note" action="All notes" onAction={() => openTab("timeline", patientId, "notes")}>
        {lastNote ? <article className="rounded-lg border border-hairline bg-ivory p-4"><time className="text-[12px] text-ink-faint" dateTime={lastNote.at}>{formatDate(lastNote.at)}</time><p className="mt-2 whitespace-pre-line text-[14px] leading-relaxed text-ink">{lastNote.text}</p></article> : <p className="text-sm text-ink-faint">No previous visit note recorded.</p>}
      </OverviewSection>

      <section className="mt-7">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 className="font-sans text-[15px] font-semibold">Vitals</h2><div className="flex flex-wrap items-center gap-4"><button type="button" onClick={() => openTab("vitals", patientId)} className="text-[12px] text-jade-700 hover:underline">All vitals →</button><VitalsDialog patientId={patientId} /></div></div>
        <MeasurementList series={vitals} expected={VITALS} showChange />
        {weight && <div className="[&>div]:border-t-0"><MeasurementList series={[{ ...weight, name: "Weight" }]} showChange /></div>}
      </section>

      <div className="mt-7 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-hairline bg-ivory p-4"><div><p className="text-[13px] font-semibold">Today’s visit</p><p className="mt-1 text-[12px] text-ink-soft">Document separately from the longitudinal record.</p></div><button type="button" className="rounded-md bg-jade-900 px-3 py-2 text-[13px] font-medium text-white" onClick={() => openTab("visit", patientId)}>Open visit draft</button></div>
      <div className="mt-5 flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2 border-y border-hairline py-4 text-[13px]"><p className="eyebrow">Next scheduled visit</p><p className="font-semibold">{patient.nextAppointment ? formatDate(patient.nextAppointment.at) : "Not scheduled"}</p></div>

      <div className="mt-7 divide-y divide-hairline border-y border-hairline">
        <OverviewDisclosure key={`problems-${patientId}`} title="Active problems" count={problems.length} action="Open problem list" onAction={() => openTab("problems", patientId)}>
          {problems.length ? <ul className="divide-y divide-hairline">{problems.map((p) => <li key={p.id} className="py-3 first:pt-0"><button type="button" className="text-left text-[14px] font-semibold text-jade-700 hover:underline" onClick={() => openTab("region", patientId, p.regionKey)}>{p.name}</button><p className="mt-1 text-[12px] text-ink-faint"><span className="capitalize">{p.status}</span> · Onset {p.onset ? formatDate(p.onset) : "not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active problems recorded.</p>}
        </OverviewDisclosure>
        <OverviewDisclosure key={`medications-${patientId}`} title="Active medications" count={meds.length} action="Open medication list" onAction={() => openTab("medications", patientId)}>
          {meds.length ? <ul className="divide-y divide-hairline">{meds.map((m) => <li key={m.id} className="py-3 first:pt-0"><p className="text-[14px] font-semibold">{m.name} <span className="font-normal">{m.dose}</span></p><p className="mt-1 text-[12px] text-ink-soft">{m.route || "Route not recorded"} · {m.frequency || "Frequency not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active medication records.</p>}
        </OverviewDisclosure>
      </div>

      <OverviewSection title="Recent chart activity" action="Full timeline" onAction={() => openTab("timeline", patientId)}><ol className="divide-y divide-hairline">{[...patient.notes].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 3).map((n) => <li key={n.id} className="flex flex-wrap gap-x-5 gap-y-2 py-3 text-[13px]"><time className="w-24 shrink-0 text-ink-faint" dateTime={n.at}>{formatDate(n.at)}</time><div className="min-w-0 flex-1 basis-48"><p className="mb-1 text-[11px] capitalize text-ink-faint">{n.kind}</p><p className="line-clamp-2 leading-relaxed">{n.text}</p></div></li>)}</ol>{!patient.notes.length && <p className="text-sm text-ink-faint">No chart activity recorded.</p>}</OverviewSection>
    </Page>
  );
}

function OverviewDisclosure({ title, count, action, onAction, children }: { title: string; count: number; action: string; onAction: () => void; children: ReactNode }) {
  return <details className="group py-5">
    <summary className="flex cursor-pointer list-none items-center gap-3 [&::-webkit-details-marker]:hidden">
      <h2 className="min-w-0 flex-1 font-sans text-[15px] font-semibold">{title}</h2>
      <span className="shrink-0 text-[12px] text-ink-soft"><span className="numeric">{count}</span> recorded</span>
      <ChevronDown aria-hidden className="size-4 shrink-0 text-jade-700 transition-transform group-open:rotate-180" />
    </summary>
    <div className="pt-4"><div className="mb-4 flex justify-end"><button type="button" onClick={onAction} className="text-[12px] text-jade-700 hover:underline">{action} →</button></div>{children}</div>
  </details>;
}

function OverviewSection({ title, action, onAction, children, className = "mt-7" }: { title: string; action: string; onAction: () => void; children: ReactNode; className?: string }) {
  return <section className={className}><div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-sans text-[15px] font-semibold">{title}</h2><button type="button" onClick={onAction} className="text-[12px] text-jade-700 hover:underline">{action} →</button></div>{children}</section>;
}
