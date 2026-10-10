"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { bloodPressure, isVital, weightTrend } from "@/lib/clinical";
import { Page, PageHeader } from "@/components/system/primitives";
import { ObservationChart } from "@/components/charts/observation-chart";
import { VitalsEntry } from "@/components/chart-entry/entry-form";

export function VitalsTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [period, setPeriod] = useState("all");
  if (!patient) return null;
  const cutoff = new Date();
  cutoff.setUTCMonth(cutoff.getUTCMonth() - Number(period));
  const series = patient.trends.map((t) => ({ ...t, points: t.points.filter((p) => period === "all" || Date.parse(p.at) >= cutoff.getTime()) }));
  const bp = bloodPressure(series);
  const weight = weightTrend(series);
  const rest = series.filter((t) => !bp.includes(t) && t !== weight);
  const otherVitals = rest.filter(isVital);
  const labs = rest.filter((t) => !isVital(t));
  const empty = period === "all" ? "No measurements recorded for this patient." : "No measurements in this period. Choose All recorded to see earlier data.";
  return <Page wide>
    <PageHeader eyebrow="Measurements" title="Vitals & trends">
      Recorded values and collection dates. Select any point for its source, or expand the table to review exact results.
    </PageHeader>
    <VitalsEntry patientId={patientId} />
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-y border-hairline py-3">
      <label className="flex items-center gap-3 text-[13px] text-ink-soft">Date range
        <select value={period} onChange={(e) => setPeriod(e.target.value)} className="rounded-md border border-hairline-strong bg-white px-3 py-2 text-ink">
          <option value="all">All recorded</option><option value="12">Last 12 months</option><option value="6">Last 6 months</option>
        </select>
      </label>
      <span className="text-[12px] text-ink-faint">{series.reduce((n, t) => n + t.points.length, 0)} recorded measurements</span>
    </div>
    <section className="mt-6"><h2 className="mb-4 font-sans text-[15px] font-semibold">Vital signs & body measurements</h2>
      <div className="grid gap-4 @min-[700px]:grid-cols-2">
        <ObservationChart title="Blood pressure" series={bp} emptyText={empty} />
        <ObservationChart title="Weight" series={weight ? [weight] : []} emptyText={empty} />
        {otherVitals.map((t) => <ObservationChart key={`${t.name}-${t.unit}`} title={t.name} series={[t]} emptyText={empty} />)}
      </div>
    </section>
    <section className="mt-8"><h2 className="mb-2 font-sans text-[15px] font-semibold">Lab & other clinical measurements</h2>
      <p className="mb-4 text-[12px] text-ink-faint">Source-specific reference intervals and individualized targets are not supplied with these records.</p>
      {labs.length ? <div className="grid gap-4 @min-[700px]:grid-cols-2">{labs.map((t) => <ObservationChart key={`${t.name}-${t.unit}`} title={t.name} series={[t]} emptyText={empty} />)}</div> : <p className="text-sm text-ink-faint">No other measurements recorded.</p>}
    </section>
  </Page>;
}
