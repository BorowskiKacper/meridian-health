"use client";

import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { useStore } from "@/lib/store";
import { formatDate } from "@/lib/data";
import { bloodPressure, isVital, weightTrend } from "@/lib/clinical";
import { Page, PageHeader } from "@/components/system/primitives";
import { MeasurementList } from "@/components/charts/measurement-list";
import { entryButton } from "@/components/chart-entry/entry-form";

export function OverviewTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;
  const lastVisit = [...patient.encounters].sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
  const problems = patient.problems.filter((p) => p.status !== "resolved");
  const meds = patient.medications.filter((m) => m.status === "active");
  const weight = weightTrend(patient.trends);
  const labs = patient.trends.filter((t) => !isVital(t));
  const due = patient.reminders.filter((r) => r.status !== "done" && r.status !== "paused").sort((a, b) => a.dueOn.localeCompare(b.dueOn));
  return (
    <Page wide>
      <PageHeader eyebrow="Longitudinal record" title="Chart overview" actions={<button type="button" className="flex h-9 items-center gap-2 rounded-md border border-hairline-strong px-3 text-[13px] text-jade-700 hover:bg-jade-50" onClick={() => openTab("body", patientId)}>Explore anatomy <ArrowUpRight className="size-3.5" /></button>} />
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-hairline bg-ivory p-4"><div><p className="text-[13px] font-semibold">Today’s visit</p><p className="mt-1 text-[12px] text-ink-soft">Document separately from the longitudinal record.</p></div><div className="flex flex-wrap gap-2"><button type="button" className={entryButton} onClick={() => openTab("vitals", patientId)}>Record vitals</button><button type="button" className="rounded-md bg-jade-900 px-3 py-2 text-[13px] font-medium text-white" onClick={() => openTab("visit", patientId)}>Open visit draft</button></div></div>
      <div className="mt-5 flex flex-wrap justify-between gap-x-8 gap-y-5 border-y border-hairline py-4 text-[13px]">
        <div className="min-w-0 flex-1 basis-56"><p className="eyebrow">Last recorded encounter</p><p className="mt-1.5 font-semibold">{lastVisit ? formatDate(lastVisit.at) : "Not recorded"}</p>{lastVisit && <details className="mt-1 text-ink-soft"><summary className="cursor-pointer text-[12px]">Encounter summary</summary><p className="mt-2 leading-relaxed">{lastVisit.summary}</p></details>}</div>
        <div className="min-w-0 flex-1 basis-56 text-right"><p className="eyebrow">Next scheduled visit</p><p className="mt-1.5 font-semibold">{patient.nextAppointment ? formatDate(patient.nextAppointment.at) : "Not recorded"}</p><p className="mt-1 text-ink-soft">{patient.nextAppointment?.reason ?? "No scheduled appointment in this chart."}</p></div>
      </div>

      <OverviewSection title="Latest vitals" action="All vitals & trends" onAction={() => openTab("vitals", patientId)}>
        <MeasurementList series={[...bloodPressure(patient.trends), ...(weight ? [weight] : []), ...patient.trends.filter((trend) => /^heart rate$|^pulse$/i.test(trend.name))]} />
      </OverviewSection>

      <div className="mt-7 divide-y divide-hairline border-y border-hairline">
        <OverviewSection className="py-5" title="Active problems" action="Problem list" onAction={() => openTab("problems", patientId)}>
          {problems.length ? <ul className="divide-y divide-hairline">{problems.map((p) => <li key={p.id} className="py-3 first:pt-0"><button type="button" className="text-left text-[14px] font-semibold text-jade-700 hover:underline" onClick={() => openTab("region", patientId, p.regionKey)}>{p.name}</button><p className="mt-1 text-[12px] text-ink-faint"><span className="capitalize">{p.status}</span> · Onset {p.onset ? formatDate(p.onset) : "not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active problems recorded.</p>}
        </OverviewSection>
        <OverviewSection className="py-5" title="Active medications" action="Medication list" onAction={() => openTab("medications", patientId)}>
          {meds.length ? <ul className="divide-y divide-hairline">{meds.map((m) => <li key={m.id} className="py-3 first:pt-0"><p className="text-[14px] font-semibold">{m.name} <span className="font-normal">{m.dose}</span></p><p className="mt-1 text-[12px] text-ink-soft">{m.route || "Route not recorded"} · {m.frequency || "Frequency not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active medication records.</p>}
        </OverviewSection>
      </div>

      <OverviewSection title="Latest diagnostic results" action="Diagnostics & sources" onAction={() => openTab("lab", patientId)}>
        <MeasurementList series={labs} limit={4} />
      </OverviewSection>
      <OverviewSection title="Follow-up on record" action="View follow-up" onAction={() => openTab("reminders", patientId)}>
        {due.length ? <ul className="divide-y divide-hairline">{due.slice(0, 4).map((r) => <li key={r.id} className="flex flex-wrap justify-between gap-2 py-3 text-[13px]"><span>{r.title}</span><span className="text-ink-soft">Due {formatDate(r.dueOn)} · {r.status === "sent" ? "Reminder sent" : r.status}</span></li>)}</ul> : <p className="text-sm text-ink-faint">No open follow-up items recorded.</p>}
      </OverviewSection>
      <OverviewSection title="Recent chart activity" action="Full timeline" onAction={() => openTab("timeline", patientId)}><ol className="divide-y divide-hairline">{[...patient.notes].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 3).map((n) => <li key={n.id} className="flex flex-wrap gap-x-5 gap-y-2 py-3 text-[13px]"><time className="w-24 shrink-0 text-ink-faint" dateTime={n.at}>{formatDate(n.at)}</time><div className="min-w-0 flex-1 basis-48"><p className="mb-1 text-[11px] capitalize text-ink-faint">{n.kind}</p><p className="line-clamp-2 leading-relaxed">{n.text}</p></div></li>)}</ol>{!patient.notes.length && <p className="text-sm text-ink-faint">No chart activity recorded.</p>}</OverviewSection>
      <button type="button" className="mt-7 text-[13px] text-jade-700 hover:underline" onClick={() => openTab("history", patientId)}>Family history, procedures & coverage →</button>
    </Page>
  );
}

function OverviewSection({ title, action, onAction, children, className = "mt-7" }: { title: string; action: string; onAction: () => void; children: ReactNode; className?: string }) {
  return <section className={className}><div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-sans text-[15px] font-semibold">{title}</h2><button type="button" onClick={onAction} className="text-[12px] text-jade-700 hover:underline">{action} →</button></div>{children}</section>;
}
