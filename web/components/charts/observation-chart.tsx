"use client";

import { useId, useState } from "react";
import { formatDate, formatMonth } from "@/lib/data";
import { recordedPoints, sourceLabel } from "@/lib/clinical";
import type { Trend, TrendPoint } from "@/lib/types";

const W = 520;
const H = 176;
const P = { left: 46, right: 20, top: 14, bottom: 28 };
const colors = ["var(--jade-600)", "var(--ink-soft)"];

export function ObservationChart({ title, series, emptyText = "No measurements recorded.", markers = [], compact = false, hideLatest = false }: {
  title: string;
  series: Trend[];
  emptyText?: string;
  markers?: { at: string; label: string }[];
  compact?: boolean;
  hideLatest?: boolean;
}) {
  const id = useId();
  const [selected, setSelected] = useState<{ series: string; at: string; value: number } | null>(null);
  const lines = series.map((s) => ({ ...s, points: recordedPoints(s) })).filter((s) => s.points.length);
  const all = lines.flatMap((s) => s.points);
  const units = new Set(lines.map((s) => s.unit));

  // Unlike units must never share an axis.
  if (units.size > 1) return <div className="space-y-4">{lines.map((s) => <ObservationChart key={`${s.name}-${s.unit}`} title={s.name} series={[s]} markers={markers} compact={compact} hideLatest={hideLatest} />)}</div>;
  if (!all.length) return (
    <section className="flex min-h-56 flex-col rounded-lg border border-hairline px-4 py-4" aria-label={title}>
      <h3 className="font-sans text-sm font-semibold">{title}</h3>
      <div className="flex flex-1 items-center py-8 text-[13px] leading-relaxed text-ink-faint">{emptyText}</div>
      <p className="text-[11px] text-ink-faint">No values have been inferred.</p>
    </section>
  );

  const times = all.map((p) => Date.parse(p.at));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const values = all.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const margin = Math.max((max - min) * 0.2, Math.abs(max) * 0.04, 0.1);
  const low = min >= 0 ? Math.max(0, min - margin) : min - margin;
  const high = max + margin;
  const x = (at: string | number) => P.left + (t0 === t1 ? (W - P.left - P.right) / 2 : (new Date(at).getTime() - t0) / (t1 - t0) * (W - P.left - P.right));
  const y = (value: number) => P.top + (high - value) / (high - low) * (H - P.top - P.bottom);
  const latest = [...all].sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0]!;
  const activeSeries = lines.find((s) => s.name === selected?.series);
  const active = activeSeries?.points.find((p) => p.at === selected?.at && p.value === selected.value);
  const unit = lines[0]!.unit || "Unit not recorded";
  const ticks = [low, (low + high) / 2, high];
  const select = (name: string, p: TrendPoint) => setSelected({ series: name, at: p.at, value: p.value });
  const rows = lines.flatMap((s) => s.points.map((p) => ({ ...p, name: s.name, unit: s.unit })))
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at));

  return (
    <figure className={`min-w-0 rounded-lg border border-hairline bg-white px-4 pt-4 pb-3${compact ? " max-w-xl" : ""}`} aria-label={`${title} trend`}>
      <figcaption>
        <div className={hideLatest ? "sr-only" : "flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1"}>
          <h3 className="font-sans text-sm font-semibold">{title}</h3>
          <span className="text-[11px] text-ink-faint">{unit}</span>
        </div>
        {!hideLatest && <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {lines.map((s, index) => {
            const last = s.points.at(-1)!;
            return <div key={`${s.name}-${s.unit}`} className="text-[12px] text-ink-soft">
              {lines.length > 1 && <span className="mr-2 inline-block w-5 align-middle" style={{ borderTop: `2px ${index ? "dashed" : "solid"} ${colors[index % colors.length]}` }} />}
              {lines.length > 1 && <span>{s.name.replace(/ blood pressure/i, "")} </span>}
              <strong className="numeric text-xl font-semibold text-jade-900">{last.value}</strong>
              <span className="mt-1 block text-[11px]">{formatDate(last.at)}</span>
            </div>;
          })}
        </div>}
        {hideLatest && lines.length > 1 && <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-[12px] text-ink-soft">{lines.map((s, index) => <span key={`${s.name}-${s.unit}`}><span className="mr-2 inline-block w-5 align-middle" style={{ borderTop: `2px ${index ? "dashed" : "solid"} ${colors[index % colors.length]}` }} />{s.name.replace(/ blood pressure/i, "")}</span>)}</div>}
        {title === "Blood pressure" && lines.length === 1 && <p className="mt-1 text-[11px] text-ink-faint">{lines[0]!.name} only; the other component is not recorded.</p>}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-labelledby={`${id}-title`} className={compact ? "mt-3 h-32 w-full overflow-visible" : "mt-3 max-h-48 w-full overflow-visible"}>
        <title id={`${id}-title`}>{title}: recorded measurements from {formatDate(t0)} to {formatDate(t1)}. Focus or select a point for its value and source.</title>
        {ticks.map((v, i) => <g key={i}>
          <line x1={P.left} x2={W - P.right} y1={y(v)} y2={y(v)} stroke="var(--hairline)" />
          <text x={P.left - 8} y={y(v) + 4} textAnchor="end" fontSize="11" className="fill-ink-faint">{Number(v.toFixed(Math.abs(v) < 10 ? 1 : 0))}</text>
        </g>)}
        <text x={P.left} y={H - 5} fontSize="11" className="fill-ink-faint">{formatMonth(t0)}</text>
        {t1 !== t0 && <text x={W - P.right} y={H - 5} textAnchor="end" fontSize="11" className="fill-ink-faint">{formatMonth(t1)}</text>}
        {markers.filter((m) => Date.parse(m.at) >= t0 && Date.parse(m.at) <= t1).map((m) => <line key={`${m.at}-${m.label}`} x1={x(m.at)} x2={x(m.at)} y1={P.top} y2={H - P.bottom} stroke="var(--watch)" strokeDasharray="2 4"><title>{m.label} · {formatDate(m.at)}</title></line>)}
        {lines.map((s, index) => <g key={`${s.name}-${s.unit}`}>
          {s.points.length > 1 && <path d={s.points.map((p, i) => `${i ? "L" : "M"}${x(p.at)},${y(p.value)}`).join(" ")} fill="none" stroke={colors[index % colors.length]} strokeWidth="2" strokeDasharray={index ? "5 4" : undefined} />}
          {s.points.map((p, i) => <g key={p.id ?? `${p.at}-${i}`} role="button" tabIndex={0}
            aria-label={`${s.name}: ${p.value} ${s.unit}, ${formatDate(p.at)}, ${sourceLabel(p.source)}`}
            onMouseEnter={() => select(s.name, p)} onFocus={() => select(s.name, p)} onClick={() => select(s.name, p)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(s.name, p); } }} className="cursor-pointer">
            <circle cx={x(p.at)} cy={y(p.value)} r="10" fill="transparent" />
            <circle cx={x(p.at)} cy={y(p.value)} r={active === p ? 5 : 3.5} fill="white" stroke={colors[index % colors.length]} strokeWidth="2" />
          </g>)}
        </g>)}
      </svg>
      <p className="mt-2 min-h-8 text-[11px] leading-relaxed text-ink-soft" aria-live="polite">
        {active ? <>{activeSeries!.name}: <strong>{active.value} {unit}</strong> · {formatDate(active.at)} · {sourceLabel(active.source)}</> : <>Latest recorded {formatDate(latest.at)} · {sourceLabel(latest.source)}{all.length === 1 ? " · One measurement; trend unavailable." : " · Select a point to inspect."}</>}
      </p>
      <details className="mt-2 border-t border-hairline pt-2 text-[12px]">
        <summary className="cursor-pointer text-jade-700">Recorded values ({all.length})</summary>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <caption className="sr-only">{title}: measurement dates, values and sources</caption>
            <thead className="text-ink-faint"><tr><th className="pb-2 pr-3 font-medium">Date</th><th className="pb-2 pr-3 font-medium">Measurement</th><th className="pb-2 font-medium">Source</th></tr></thead>
            <tbody className="divide-y divide-hairline">{rows.map((p, i) => <tr key={`${p.id ?? p.at}-${i}`}><td className="py-2 pr-3 align-top whitespace-nowrap">{formatDate(p.at)}</td><td className="py-2 pr-3 align-top">{lines.length > 1 ? `${p.name}: ` : ""}<strong className="numeric font-semibold">{p.value} {p.unit}</strong></td><td className="py-2 align-top">{sourceLabel(p.source)}{p.documentId && <span className="mt-1 block break-all text-ink-faint">Document {p.documentId}</span>}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
