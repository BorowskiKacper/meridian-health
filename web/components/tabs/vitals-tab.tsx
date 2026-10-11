"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { bloodPressure, isVital, recordedPoints, sourceLabel, weightTrend } from "@/lib/clinical";
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
  const measurements = series.filter(isVital).flatMap((t) => recordedPoints(t).map((p) => ({ ...p, name: t.name, unit: t.unit }))).sort((a, b) => b.at.localeCompare(a.at));
  const diastolic = new Map(recordedPoints(bp[1] ?? { name: "", unit: "", points: [] }).map((p) => [`${p.at}:${p.source ?? ""}`, p.value]));
  const pairs = recordedPoints(bp[0] ?? { name: "", unit: "", points: [] }).flatMap((p) => {
    const d = diastolic.get(`${p.at}:${p.source ?? ""}`);
    return d === undefined ? [] : [{ systolic: p.value, diastolic: d }];
  });
  const mean = pairs.length ? `${(pairs.reduce((n, p) => n + p.systolic, 0) / pairs.length).toFixed(1)}/${(pairs.reduce((n, p) => n + p.diastolic, 0) / pairs.length).toFixed(1)}` : null;
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
      <span className="text-[12px] text-ink-faint">{measurements.length} recorded vital measurements</span>
    </div>
    {mean && <div className="mt-5 flex flex-wrap justify-between gap-3 rounded-md border border-hairline bg-ivory p-4"><div><p className="text-[12px] text-ink-soft">Average recorded blood pressure · selected period</p><p className="mt-1 text-[11px] text-ink-faint">{pairs.length} paired readings at matching times and sources · arithmetic mean</p></div><p className="numeric text-[18px] font-semibold">{mean} <span className="text-[12px] font-normal text-ink-soft">mmHg</span></p></div>}
    <section className="mt-6"><h2 className="mb-4 font-sans text-[15px] font-semibold">Vital signs & body measurements</h2>
      <div className="grid gap-4 @min-[700px]:grid-cols-2">
        {bp.some((t) => t.points.length) && <ObservationChart title="Blood pressure" series={bp} compact emptyText={empty} />}
        {weight?.points.length ? <ObservationChart title="Weight" series={[weight]} compact emptyText={empty} /> : null}
        {otherVitals.filter((t) => t.points.length).map((t) => <ObservationChart key={`${t.name}-${t.unit}`} title={t.name} series={[t]} compact emptyText={empty} />)}
      </div>
      {!measurements.length && <p className="border-y border-hairline py-5 text-sm text-ink-soft">{empty}</p>}
    </section>
    <details className="mt-7"><summary className="cursor-pointer text-[13px] font-medium text-jade-700">Vitals flowsheet · exact values & sources</summary><div className="mt-4 overflow-x-auto" role="region" aria-label="Vitals flowsheet" tabIndex={0}><table className="clinical-table min-w-[520px]"><thead><tr>{["Measured at (local)", "Vital sign", "Value", "Source"].map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{measurements.map((p, i) => <tr key={p.id || `${p.at}-${i}`}><td><time dateTime={p.at}>{new Date(p.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</time></td><td>{p.name}</td><td className="numeric">{p.value} {p.unit}</td><td>{sourceLabel(p.source)}</td></tr>)}</tbody></table></div></details>
    <p className="mt-6 text-[12px] text-ink-faint">Diagnostic results have their own chart section. Wearable feeds are not connected; all values here are recorded chart measurements.</p>
  </Page>;
}
