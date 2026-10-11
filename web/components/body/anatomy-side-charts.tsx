"use client";

import { useId } from "react";
import { recordedPoints, sourceLabel } from "@/lib/clinical";
import { formatDate, formatMonth } from "@/lib/data";
import { referenceFor } from "@/lib/reference";
import type { Finding, Trend } from "@/lib/types";
import { cn } from "@/lib/utils";
import { TrendArrow } from "@/components/charts/trend-arrow";

function fmt(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return String(Number(value.toFixed(1)));
  return String(Number(value.toFixed(2)));
}

const sameTrend = (a: Trend, b: Trend) => a.name === b.name && a.unit === b.unit;

/** Trend charts for the region selected on the 3D model. */
export function RegionCharts({ finding }: { finding: Finding }) {
  const trends = finding.trends.map((t) => ({ ...t, points: recordedPoints(t) })).filter((t) => t.points.length);
  if (!trends.length) return <p className="mt-3 text-[12px] text-ink-faint">No measurements are charted on this region.</p>;
  return <div className="mt-3 space-y-3">{trends.map((t) => <RegionChart key={`${t.name}-${t.unit}`} trend={t} />)}</div>;
}

function RegionChart({ trend }: { trend: Trend }) {
  const id = useId();
  const W = 280, H = 92, L = 32, R = 10, T = 10, B = 20;
  const points = trend.points;
  const last = points[points.length - 1];
  const ref = referenceFor(trend.name);
  const values = [...points.map((p) => p.value), ref?.low, ref?.high].filter((v): v is number => v !== undefined);
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.1 || 1;
  const d0 = lo - pad, d1 = hi + pad;
  const t0 = Date.parse(points[0].at), t1 = Date.parse(last.at);
  const x = (at: string) => (t0 === t1 ? (L + W - R) / 2 : L + ((Date.parse(at) - t0) / (t1 - t0)) * (W - L - R));
  const y = (v: number) => T + ((d1 - v) / (d1 - d0)) * (H - T - B);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.at)},${y(p.value)}`).join(" ");
  const area = `${line} L${x(last.at)},${H - B} L${x(points[0].at)},${H - B} Z`;

  return <figure className="rounded-lg border border-hairline bg-white p-3">
    <figcaption className="flex items-baseline justify-between gap-2">
      <span className="truncate text-[12px] font-medium text-ink">{trend.name}</span>
      <span className="numeric shrink-0 text-[12px]"><strong className="text-[15px] text-jade-900">{fmt(last.value)}</strong> <span className="text-ink-faint">{trend.unit}</span></span>
    </figcaption>
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-1.5 w-full overflow-visible" role="img" aria-label={`${trend.name}: ${points.length} results from ${formatDate(points[0].at)} to ${formatDate(last.at)}, latest ${last.value} ${trend.unit}`}>
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--jade-600)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--jade-600)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {ref && <rect x={L} width={W - L - R} y={y(ref.high ?? d1)} height={y(ref.low ?? d0) - y(ref.high ?? d1)} fill="var(--jade-50)" stroke="var(--jade-300)" strokeDasharray="3 3"><title>{`Display reference: ${ref.label}`}</title></rect>}
      {[d1 - pad, d0 + pad].map((v) => <text key={v} x={L - 6} y={y(v) + 3.5} textAnchor="end" fontSize="10" className="fill-ink-faint">{fmt(v)}</text>)}
      {points.length > 1 && <>
        <path d={area} fill={`url(#${id}-fill)`} />
        <path d={line} fill="none" stroke="var(--jade-600)" strokeWidth="2" strokeLinejoin="round" />
      </>}
      {points.map((p, i) => <circle key={p.id ?? `${p.at}-${i}`} cx={x(p.at)} cy={y(p.value)} r={p === last ? 4.5 : 3} fill={p === last ? "var(--jade-600)" : "white"} stroke="var(--jade-600)" strokeWidth="1.8">
        <title>{`${p.value} ${trend.unit} · ${formatDate(p.at)} · ${sourceLabel(p.source)}`}</title>
      </circle>)}
      <text x={L} y={H - 4} fontSize="10" className="fill-ink-faint">{formatMonth(points[0].at)}</text>
      {t1 !== t0 && <text x={W - R} y={H - 4} textAnchor="end" fontSize="10" className="fill-ink-faint">{formatMonth(last.at)}</text>}
    </svg>
    <p className="mt-1 text-[11px] text-ink-faint">{points.length === 1 ? "One result; no trend yet" : `${points.length} results`} · latest {formatDate(last.at)}{ref ? " · shaded band is a display default, not lab-issued" : ""}</p>
  </figure>;
}

/** Every charted measurement as a sparkline; choosing one flies the model to its region. */
export function MeasurementSparks({ trends, findings, activeId, onPick }: {
  trends: Trend[];
  findings: Finding[];
  activeId: string;
  onPick: (findingId: string) => void;
}) {
  const rows = trends.map((t) => ({ ...t, points: recordedPoints(t) })).filter((t) => t.points.length);
  if (!rows.length) return <p className="mt-3 text-[12px] text-ink-faint">No measurements recorded.</p>;
  return <ul className="mt-2 divide-y divide-hairline">
    {rows.map((t) => {
      const owner = findings.find((f) => f.trends.some((ft) => sameTrend(ft, t)));
      const active = owner?.id === activeId;
      const last = t.points[t.points.length - 1];
      return <li key={`${t.name}-${t.unit}`}>
        <button type="button" disabled={!owner} onClick={() => owner && onPick(owner.id)}
          title={owner ? `Show ${owner.title} on the model` : "Not linked to a region on the model"}
          className={cn("grid w-full grid-cols-[minmax(0,1fr)_72px_auto] items-center gap-3 rounded-md px-2 py-2 text-left transition-colors enabled:hover:bg-jade-50 disabled:cursor-default", active && "bg-jade-50")}>
          <span className="min-w-0">
            <span className="block truncate text-[12px] font-medium text-ink">{t.name}</span>
            <span className="block truncate text-[10.5px] text-ink-faint">{owner ? owner.title : "No region"} · {formatMonth(last.at)}</span>
          </span>
          <Sparkline trend={t} />
          <span className="numeric flex items-center gap-1 text-[12px] text-ink"><strong className="font-semibold">{fmt(last.value)}</strong><span className="text-[10.5px] text-ink-faint">{t.unit}</span><TrendArrow trend={t} className="size-3" /></span>
        </button>
      </li>;
    })}
  </ul>;
}

function Sparkline({ trend }: { trend: Trend }) {
  const W = 72, H = 24, P = 3;
  const values = trend.points.map((p) => p.value);
  const lo = Math.min(...values), hi = Math.max(...values);
  const x = (i: number) => (values.length === 1 ? W / 2 : P + (i / (values.length - 1)) * (W - P * 2));
  const y = (v: number) => (hi === lo ? H / 2 : P + ((hi - v) / (hi - lo)) * (H - P * 2));
  return <svg viewBox={`0 0 ${W} ${H}`} className="h-6 w-[72px] overflow-visible" aria-hidden>
    {values.length > 1 && <polyline points={values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} fill="none" stroke="var(--jade-600)" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />}
    <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r="2.6" fill="var(--jade-600)" />
  </svg>;
}
