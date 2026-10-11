"use client";

import { useState, type CSSProperties, type ReactNode } from "react";
import { isVital, recordedPoints, sourceLabel } from "@/lib/clinical";
import { formatDate, formatMonth } from "@/lib/data";
import { referenceFor } from "@/lib/reference";
import type { Trend, TrendPoint } from "@/lib/types";

const PALETTE = ["#28634f", "#c08a2e", "#4f7f9e", "#8fbfa8", "#00362d", "#a0708f", "#6b8f3a", "#5e6b66"];

type Series = Trend & { points: TrendPoint[]; color: string };
type Scope = "all" | "labs";

function delay(ms: number): CSSProperties {
  return { animationDelay: `${ms}ms` };
}

function fmt(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return String(Number(value.toFixed(1)));
  return String(Number(value.toFixed(2)));
}

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export function DiagnosticAnalytics({ trends, query }: { trends: Trend[]; query: string }) {
  const [scope, setScope] = useState<Scope>("all");
  const needle = query.toLowerCase();
  const series: Series[] = trends
    .map((t, i) => ({ ...t, points: recordedPoints(t), color: PALETTE[i % PALETTE.length] }))
    .filter((t) => t.points.length && (scope === "all" || !isVital(t)) && `${t.name} ${t.unit}`.toLowerCase().includes(needle));
  const labCount = trends.filter((t) => !isVital(t) && recordedPoints(t).length).length;

  return <section className="mt-8" aria-labelledby="diagnostic-analytics">
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="eyebrow">Visual analytics</p>
        <h2 id="diagnostic-analytics" className="mt-1 text-[22px] leading-tight">Measurement overview</h2>
      </div>
      <div role="group" aria-label="Measurements to chart" className="inline-flex rounded-full border border-hairline-strong bg-ivory p-0.5 text-[12px]">
        {([["all", "All measurements"], ["labs", `Diagnostics only · ${labCount}`]] as const).map(([key, label]) =>
          <button key={key} type="button" aria-pressed={scope === key} onClick={() => setScope(key)}
            className={`rounded-full px-3 py-1.5 transition-colors ${scope === key ? "bg-jade-600 text-white shadow-sm" : "text-ink-soft hover:text-jade-900"}`}>{label}</button>)}
      </div>
    </div>
    {series.length ? <div key={`${scope}:${needle}`} className="grid gap-4 @min-[760px]:grid-cols-2">
      <SummaryTiles series={series} />
      <Distribution series={series} />
      <LatestVsReference series={series} />
      <CoverageHeatmap series={series} />
    </div> : <p className="rounded-xl border border-dashed border-hairline-strong bg-ivory px-5 py-8 text-center text-[13px] text-ink-soft">
      {scope === "labs" ? "No diagnostic results to chart. Switch to All measurements to include vital signs." : "No recorded measurements match this view."}
    </p>}
  </section>;
}

function Card({ title, subtitle, children, className = "" }: { title: string; subtitle?: string; children: ReactNode; className?: string }) {
  return <figure className={`chart-fade min-w-0 rounded-xl border border-hairline bg-white p-4 shadow-[0_1px_2px_rgb(0_54_45/0.05)] ${className}`}>
    <figcaption className="mb-3">
      <h3 className="font-sans text-sm font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-0.5 text-[11px] leading-relaxed text-ink-faint">{subtitle}</p>}
    </figcaption>
    {children}
  </figure>;
}

function SummaryTiles({ series }: { series: Series[] }) {
  const points = series.flatMap((s) => s.points.map((p) => ({ ...p, name: s.name })));
  const sorted = [...points].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const sources = new Set(points.map((p) => p.source ?? "unknown"));
  const tiles = [
    { label: "Measurements", value: String(series.length), detail: `${series.filter((s) => !isVital(s)).length} diagnostic · ${series.filter(isVital).length} vital` },
    { label: "Results", value: String(points.length), detail: `${(points.length / series.length).toFixed(1)} per measurement` },
    { label: "Collection span", value: first === last ? formatMonth(first.at) : `${new Date(first.at).getUTCFullYear()}–${new Date(last.at).getUTCFullYear()}`, detail: `${formatMonth(first.at)} to ${formatMonth(last.at)}` },
    { label: "Latest result", value: formatDate(last.at), detail: `${last.name} · ${sources.size} source${sources.size === 1 ? "" : "s"}` },
  ];
  return <div className="grid grid-cols-2 gap-3 @min-[760px]:col-span-2 @min-[1000px]:grid-cols-4">
    {tiles.map((tile, i) => <div key={tile.label} className="chart-fade relative overflow-hidden rounded-xl border border-hairline bg-linear-to-br from-jade-50 via-white to-white p-4" style={delay(i * 70)}>
      <span aria-hidden className="absolute -top-6 -right-6 size-20 rounded-full bg-jade-100/60" />
      <p className="eyebrow relative">{tile.label}</p>
      <p className="numeric relative mt-2 text-[22px] leading-none font-semibold text-jade-900">{tile.value}</p>
      <p className="relative mt-2 truncate text-[11px] text-ink-faint">{tile.detail}</p>
    </div>)}
  </div>;
}

function Distribution({ series }: { series: Series[] }) {
  const W = 620, H = 46, PAD = 12;
  return <Card title="Distribution by measurement" subtitle="Box plots · median, interquartile box, 1.5×IQR whiskers and every recorded value. Each row has its own scale." className="@min-[760px]:col-span-2">
    <div className="divide-y divide-hairline">
      {series.map((s, row) => {
        const values = s.points.map((p) => p.value).sort((a, b) => a - b);
        const q1 = quantile(values, 0.25), med = quantile(values, 0.5), q3 = quantile(values, 0.75);
        const iqr = q3 - q1;
        const inside = values.filter((v) => v >= q1 - 1.5 * iqr && v <= q3 + 1.5 * iqr);
        const lo = inside[0] ?? values[0], hi = inside[inside.length - 1] ?? values[values.length - 1];
        const ref = referenceFor(s.name);
        const domain = [values[0], values[values.length - 1], ref?.low, ref?.high].filter((v): v is number => v !== undefined);
        let d0 = Math.min(...domain), d1 = Math.max(...domain);
        const pad = (d1 - d0) * 0.08 || Math.abs(d1) * 0.1 || 1;
        d0 -= pad; d1 += pad;
        const x = (v: number) => PAD + ((v - d0) / (d1 - d0)) * (W - PAD * 2);
        const mid = H / 2 - 4;
        return <div key={s.name + s.unit} className="grid items-center gap-x-4 gap-y-1 py-3 @min-[620px]:grid-cols-[11rem_1fr_7rem]">
          <div className="min-w-0">
            <p className="flex items-center gap-2 truncate text-[13px] font-medium text-ink"><span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: s.color }} />{s.name}</p>
            <p className="mt-0.5 text-[11px] text-ink-faint">{s.unit || "Unit not recorded"} · n={values.length}</p>
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible" role="img" aria-label={`${s.name}: median ${fmt(med)}, range ${fmt(values[0])} to ${fmt(values[values.length - 1])} ${s.unit}`}>
            <line x1={PAD} x2={W - PAD} y1={mid} y2={mid} stroke="var(--hairline)" />
            {ref && <rect x={x(ref.low ?? d0)} width={x(ref.high ?? d1) - x(ref.low ?? d0)} y={mid - 15} height="30" rx="4" fill="var(--jade-50)" stroke="var(--jade-300)" strokeDasharray="3 3"><title>{`Display reference: ${ref.label}`}</title></rect>}
            {values.length > 1 && <g className="chart-stretch" style={delay(row * 80)}>
              <line x1={x(lo)} x2={x(q1)} y1={mid} y2={mid} stroke={s.color} strokeWidth="1.5" />
              <line x1={x(q3)} x2={x(hi)} y1={mid} y2={mid} stroke={s.color} strokeWidth="1.5" />
              <line x1={x(lo)} x2={x(lo)} y1={mid - 7} y2={mid + 7} stroke={s.color} strokeWidth="1.5" />
              <line x1={x(hi)} x2={x(hi)} y1={mid - 7} y2={mid + 7} stroke={s.color} strokeWidth="1.5" />
              <rect x={x(q1)} width={Math.max(x(q3) - x(q1), 2)} y={mid - 11} height="22" rx="4" fill={s.color} fillOpacity="0.18" stroke={s.color} strokeWidth="1.5" />
              <line x1={x(med)} x2={x(med)} y1={mid - 11} y2={mid + 11} stroke={s.color} strokeWidth="3" strokeLinecap="round" />
            </g>}
            {s.points.map((p, i) => {
              const outlier = values.length > 3 && (p.value < lo || p.value > hi);
              return <circle key={p.id ?? `${p.at}-${i}`} cx={x(p.value)} cy={mid + ((i * 7) % 11) - 5} r={outlier ? 4.5 : values.length === 1 ? 5 : 3}
                fill={outlier ? "white" : s.color} fillOpacity={outlier || values.length === 1 ? 1 : 0.55} stroke={outlier ? "var(--watch)" : "white"} strokeWidth={outlier ? 2 : 1}
                className="chart-fade" style={delay(row * 80 + 250 + i * 40)}>
                <title>{`${p.value} ${s.unit} · ${formatDate(p.at)} · ${sourceLabel(p.source)}${outlier ? " · statistical outlier" : ""}`}</title>
              </circle>;
            })}
            <text x={PAD} y={H - 1} fontSize="10" className="fill-ink-faint">{fmt(d0 + pad)}</text>
            <text x={W - PAD} y={H - 1} fontSize="10" textAnchor="end" className="fill-ink-faint">{fmt(d1 - pad)}</text>
          </svg>
          <p className="numeric text-[12px] text-ink-soft @min-[620px]:text-right">
            <span className="text-[10px] tracking-wide text-ink-faint uppercase">Median</span><br /><strong className="text-[15px] text-jade-900">{fmt(med)}</strong> <span className="text-[11px]">{s.unit}</span>
          </p>
        </div>;
      })}
    </div>
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-faint">
      <span className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-4 rounded-[3px] border border-dashed border-jade-300 bg-jade-50" />Display reference band (not lab-issued)</span>
      <span className="flex items-center gap-1.5"><span aria-hidden className="inline-block size-2.5 rounded-full border-2 border-watch bg-white" />Statistical outlier (beyond 1.5×IQR)</span>
    </div>
  </Card>;
}

function LatestVsReference({ series }: { series: Series[] }) {
  const rows = series.flatMap((s) => {
    const ref = referenceFor(s.name);
    return ref ? [{ s, ref, last: s.points[s.points.length - 1] }] : [];
  });
  const W = 300;

  return <Card title="Latest result against reference" subtitle="Bullet charts · latest value on the app's display reference band">
    {rows.length ? <div className="space-y-4">
      {rows.map(({ s, ref, last }, i) => {
        const span = [ref.low, ref.high].filter((v): v is number => v !== undefined);
        const width = (Math.max(...span) - Math.min(...span)) || Math.abs(span[0]) * 0.5 || 1;
        const d0 = Math.min(last.value, ref.low ?? span[0] - width) - width * 0.35;
        const d1 = Math.max(last.value, ref.high ?? span[0] + width) + width * 0.35;
        const x = (v: number) => ((v - d0) / (d1 - d0)) * W;
        const outside = (ref.low !== undefined && last.value < ref.low) || (ref.high !== undefined && last.value > ref.high);
        const color = outside ? "var(--watch)" : "var(--jade-700)";
        const range = ref.low !== undefined && ref.high !== undefined ? `${ref.low}–${ref.high}` : ref.low !== undefined ? `≥ ${ref.low}` : `< ${ref.high}`;
        return <div key={s.name + s.unit}>
          <div className="flex items-baseline justify-between gap-3 text-[12px]">
            <span className="truncate font-medium text-ink">{s.name}</span>
            <span className="numeric shrink-0"><strong style={{ color }}>{fmt(last.value)}</strong> <span className="text-ink-faint">{s.unit}</span></span>
          </div>
          <svg viewBox={`0 -4 ${W} 26`} className="mt-1 w-full overflow-visible" role="img" aria-label={`${s.name} latest ${last.value} ${s.unit}; display reference ${range}`}>
            <rect x="0" y="4" width={W} height="12" rx="6" fill="var(--ivory-deep)" />
            <rect x={x(ref.low ?? d0)} y="4" width={x(ref.high ?? d1) - x(ref.low ?? d0)} height="12" rx="6" fill="var(--jade-100)" className="chart-grow" style={delay(i * 90)} />
            <g className="chart-pop" style={{ ...delay(i * 90 + 250), transformBox: "fill-box", transformOrigin: "center" }}>
              <line x1={x(last.value)} x2={x(last.value)} y1="-2" y2="22" stroke={color} strokeWidth="3" strokeLinecap="round" />
              <circle cx={x(last.value)} cy="10" r="5" fill="white" stroke={color} strokeWidth="2.5" />
            </g>
            <title>{`${ref.label} · latest ${formatDate(last.at)}`}</title>
          </svg>
          <p className="mt-0.5 text-[11px] text-ink-faint">Display range {range} {s.unit} · {formatDate(last.at)}</p>
        </div>;
      })}
    </div> : <p className="py-6 text-[13px] text-ink-faint">No measurement in this view has a display reference band.</p>}
    <p className="mt-3 border-t border-hairline pt-2 text-[11px] leading-relaxed text-ink-faint">Bands are adult display defaults, not lab-issued intervals. Values outside a band are marked amber for visibility only; no clinical judgement is implied.</p>
  </Card>;
}

function CoverageHeatmap({ series }: { series: Series[] }) {
  const years = series.flatMap((s) => s.points.map((p) => new Date(p.at).getUTCFullYear()));
  const y0 = Math.min(...years);
  const cols = Array.from({ length: Math.max(...years) - y0 + 1 }, (_, i) => y0 + i);
  const grid = series.map((s) => cols.map((y) => s.points.filter((p) => new Date(p.at).getUTCFullYear() === y).length));
  const max = Math.max(1, ...grid.flat());

  return <Card title="Collection coverage" subtitle="Heatmap · results per measurement per year; darker cells mean more results">
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1 text-[12px]">
        <thead><tr><th scope="col" className="sr-only">Measurement</th>{cols.map((y) => <th key={y} scope="col" className="numeric px-1 pb-1 text-center text-[11px] font-medium text-ink-faint">{y}</th>)}</tr></thead>
        <tbody>
          {series.map((s, r) => <tr key={s.name + s.unit}>
            <th scope="row" className="max-w-44 truncate pr-3 text-left font-medium text-ink"><span aria-hidden className="mr-2 inline-block size-2 rounded-full align-middle" style={{ background: s.color }} />{s.name}</th>
            {grid[r].map((n, c) => <td key={cols[c]} className="p-0">
              <div className="chart-pop numeric flex h-9 min-w-12 items-center justify-center rounded-md text-[12px] font-semibold"
                style={{ ...delay((r + c) * 45), transformBox: "fill-box", transformOrigin: "center", background: n ? `color-mix(in srgb, ${s.color} ${Math.round(22 + (n / max) * 70)}%, white)` : "var(--ivory)", color: n / max > 0.5 ? "white" : n ? "var(--jade-900)" : "var(--clear)" }}
                title={`${s.name} · ${cols[c]}: ${n} result${n === 1 ? "" : "s"}`}>{n || "·"}</div>
            </td>)}
          </tr>)}
        </tbody>
      </table>
    </div>
  </Card>;
}
