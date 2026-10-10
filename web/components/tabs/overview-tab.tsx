"use client";

import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { useStore } from "@/lib/store";
import { formatDate } from "@/lib/data";
import { bloodPressure, isVital, weightTrend } from "@/lib/clinical";
import { Page, PageHeader } from "@/components/system/primitives";
import { MeasurementList } from "@/components/charts/measurement-list";
import { VitalsEntry } from "@/components/chart-entry/entry-form";

export function OverviewTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;
  const lastVisit = patient.notes.filter((n) => n.kind === "visit").sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
  const problems = patient.problems.filter((p) => p.status !== "resolved");
  const meds = patient.medications.filter((m) => m.status === "active");
  const weight = weightTrend(patient.trends);
  const labs = patient.trends.filter((t) => !isVital(t));
  const due = patient.reminders.filter((r) => r.status !== "done" && r.status !== "paused").sort((a, b) => a.dueOn.localeCompare(b.dueOn));
  return (
    <Page wide>
      <PageHeader eyebrow="Longitudinal record" title="Chart overview" actions={<button type="button" className="flex h-9 items-center gap-2 rounded-md border border-hairline-strong px-3 text-[13px] text-jade-700 hover:bg-jade-50" onClick={() => openTab("body", patientId)}>Explore anatomy <ArrowUpRight className="size-3.5" /></button>} />
      <VitalsEntry patientId={patientId} />
      <div className="mt-5 grid gap-4 border-y border-hairline py-4 text-[13px] @min-[700px]:grid-cols-2">
        <div><p className="eyebrow">Last recorded encounter</p><p className="mt-1.5 font-semibold">{lastVisit ? formatDate(lastVisit.at) : "Not recorded"}</p>{lastVisit && <details className="mt-1 text-ink-soft"><summary className="cursor-pointer text-[12px]">Encounter summary</summary><p className="mt-2 leading-relaxed">{lastVisit.text}</p></details>}</div>
        <div><p className="eyebrow">Next scheduled visit</p><p className="mt-1.5 font-semibold">{patient.nextAppointment ? formatDate(patient.nextAppointment.at) : "Not recorded"}</p><p className="mt-1 text-ink-soft">{patient.nextAppointment?.reason ?? "No scheduled appointment in this chart."}</p></div>
      </div>

      <OverviewSection title="Latest vitals" action="All vitals & trends" onAction={() => openTab("vitals", patientId)}>
        <MeasurementList series={[...bloodPressure(patient.trends), ...(weight ? [weight] : []), ...patient.trends.filter((trend) => /^heart rate$|^pulse$/i.test(trend.name))]} />
      </OverviewSection>

      <div className="grid gap-x-8 @min-[700px]:grid-cols-2">
        <OverviewSection title="Active problems" action="Problem list" onAction={() => openTab("problems", patientId)}>
          {problems.length ? <ul className="divide-y divide-hairline">{problems.map((p) => <li key={p.id} className="py-3 first:pt-0"><button type="button" className="text-left text-[14px] font-semibold text-jade-700 hover:underline" onClick={() => openTab("region", patientId, p.regionKey)}>{p.name}</button><p className="mt-1 text-[12px] text-ink-faint"><span className="capitalize">{p.status}</span> · Onset {p.onset ? formatDate(p.onset) : "not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active problems recorded.</p>}
        </OverviewSection>
        <OverviewSection title="Active medications" action="Medication list" onAction={() => openTab("medications", patientId)}>
          {meds.length ? <ul className="divide-y divide-hairline">{meds.map((m) => <li key={m.id} className="py-3 first:pt-0"><p className="text-[14px] font-semibold">{m.name} <span className="font-normal">{m.dose}</span></p><p className="mt-1 text-[12px] text-ink-soft">{m.route || "Route not recorded"} · {m.frequency || "Frequency not recorded"}</p></li>)}</ul> : <p className="text-sm text-ink-faint">No active medication records.</p>}
        </OverviewSection>
      </div>

      <OverviewSection title="Latest lab results" action="All measurements" onAction={() => openTab("vitals", patientId)}>
        <MeasurementList series={labs} limit={4} />
      </OverviewSection>
      <OverviewSection title="Follow-up on record" action="View follow-up" onAction={() => openTab("reminders", patientId)}>
        {due.length ? <ul className="divide-y divide-hairline">{due.slice(0, 4).map((r) => <li key={r.id} className="flex flex-wrap justify-between gap-2 py-3 text-[13px]"><span>{r.title}</span><span className="text-ink-soft">Due {formatDate(r.dueOn)} · {r.status === "sent" ? "Reminder sent" : r.status}</span></li>)}</ul> : <p className="text-sm text-ink-faint">No open follow-up items recorded.</p>}
      </OverviewSection>
      <details className="mt-8 border-t border-hairline pt-4 text-[13px]"><summary className="cursor-pointer font-semibold text-jade-700">Family history & coverage</summary><ul className="mt-3 space-y-2 text-ink-soft">{patient.family.length ? patient.family.map((f) => <li key={f}>{f}</li>) : <li>Family history not recorded.</li>}</ul><p className="mt-3 text-ink-soft">{patient.coverage ? `${patient.coverage.payer} · ${patient.coverage.plan} · ${patient.coverage.active ? "Active coverage" : "Inactive coverage"}` : "Coverage not recorded."}</p></details>
    </Page>
  );
}

function OverviewSection({ title, action, onAction, children }: { title: string; action: string; onAction: () => void; children: ReactNode }) {
  return <section className="mt-7"><div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 className="font-sans text-[15px] font-semibold">{title}</h2><button type="button" onClick={onAction} className="text-[12px] text-jade-700 hover:underline">{action} →</button></div>{children}</section>;
}
