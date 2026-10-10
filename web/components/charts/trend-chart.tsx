"use client";

import { useId, useState } from "react";
import { formatDate, formatMonth } from "@/lib/data";
import { flagValue, isConcerning, referenceFor } from "@/lib/reference";
import type { Trend } from "@/lib/types";
import { cn } from "@/lib/utils";

const WIDTH = 560;
const HEIGHT = 168;
const PAD = { top: 14, right: 18, bottom: 26, left: 44 };
const LINE_COLOR = "var(--jade-600)";
const BAND_COLOR = "rgb(1 118 96 / 0.08)";

interface Marker {
  at: string;
  label: string;
}

/**
 * One analyte over time with the reference band behind it. Medication starts
 * are drawn as vertical markers so a clinician can see what moved the curve.
 */
export function TrendChart({ trend, markers = [], className }: { trend: Trend; markers?: Marker[]; className?: string }) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const points = [...trend.points].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
  const range = referenceFor(trend.name);
  if (points.length === 0) return null;

  const times = points.map((point) => Date.parse(point.at));
  const values = points.map((point) => point.value);
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const bandValues = [range?.low, range?.high].filter((v): v is number => v !== undefined);
  const vMin = Math.min(...values, ...bandValues);
  const vMax = Math.max(...values, ...bandValues);
  const padV = (vMax - vMin || Math.abs(vMax) || 1) * 0.15;
  const lo = vMin - padV;
  const hi = vMax + padV;

  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (t: number) => PAD.left + (t1 === t0 ? innerW / 2 : ((t - t0) / (t1 - t0)) * innerW);
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo)) * innerH;

  const path = points.map((point, index) => `${index === 0 ? "M" : "L"}${x(times[index]!).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  const bandTop = range?.high !== undefined ? y(range.high) : PAD.top;
  const bandBottom = range?.low !== undefined ? y(range.low) : PAD.top + innerH;
  const last = points.at(-1)!;
  const concerning = isConcerning(trend.name, last.value);
  const active = hover ?? points.length - 1;
  const activePoint = points[active]!;

  const ticks = [lo + padV, (lo + hi) / 2, hi - padV].map((v) => Number(v.toFixed(v < 10 ? 1 : 0)));
  const yearTicks = yearBoundaries(t0, t1);

  return (
    <figure className={cn("rounded-lg border border-hairline bg-white px-4 pt-3 pb-2", className)}>
      <figcaption className="flex items-baseline justify-between gap-4">
        <span className="text-[14px] text-ink">{trend.name}</span>
        <span className={cn("numeric text-[15px]", concerning ? "font-semibold text-critical" : "text-jade-900")}>
          {activePoint.value} <span className="text-[12px] text-ink-faint">{trend.unit}</span>
          <span className="ml-2 text-[12px] font-normal text-ink-faint">{formatDate(activePoint.at)}</span>
        </span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby={`${id}-title`}
        className="mt-1 w-full"
        onMouseLeave={() => setHover(null)}
      >
        <title id={`${id}-title`}>
          {trend.name}, {points.length} results from {formatMonth(t0)} to {formatMonth(t1)}
        </title>
        {range && <rect x={PAD.left} width={innerW} y={Math.min(bandTop, bandBottom)} height={Math.abs(bandBottom - bandTop)} fill={BAND_COLOR} />}
        {range?.high !== undefined && <line x1={PAD.left} x2={PAD.left + innerW} y1={y(range.high)} y2={y(range.high)} stroke="rgb(1 118 96 / 0.35)" strokeDasharray="3 4" />}
        {range?.low !== undefined && <line x1={PAD.left} x2={PAD.left + innerW} y1={y(range.low)} y2={y(range.low)} stroke="rgb(1 118 96 / 0.35)" strokeDasharray="3 4" />}
        {ticks.map((tick) => (
          <text key={tick} x={PAD.left - 8} y={y(tick) + 3.5} textAnchor="end" className="fill-ink-faint" fontSize="10">
            {tick}
          </text>
        ))}
        {yearTicks.map((year) => (
          <g key={year.at}>
            <line x1={x(year.at)} x2={x(year.at)} y1={PAD.top} y2={PAD.top + innerH} stroke="rgb(0 54 45 / 0.08)" />
            <text x={x(year.at)} y={HEIGHT - 8} textAnchor="middle" className="fill-ink-faint" fontSize="10">
              {year.label}
            </text>
          </g>
        ))}
        {markers
          .filter((marker) => {
            const t = Date.parse(marker.at);
            return !Number.isNaN(t) && t >= t0 && t <= t1;
          })
          .map((marker) => (
            <g key={`${marker.at}-${marker.label}`}>
              <line x1={x(Date.parse(marker.at))} x2={x(Date.parse(marker.at))} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--watch)" strokeDasharray="2 3" />
              <text x={x(Date.parse(marker.at)) + 4} y={PAD.top + 9} className="fill-watch" fontSize="9.5">
                {marker.label}
              </text>
            </g>
          ))}
        <path d={path} fill="none" stroke={LINE_COLOR} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        {points.map((point, index) => {
          const flag = flagValue(trend.name, point.value);
          const worrying = isConcerning(trend.name, point.value);
          return (
            <g key={point.at} onMouseEnter={() => setHover(index)}>
              <circle cx={x(times[index]!)} cy={y(point.value)} r="12" fill="transparent" />
              <circle
                cx={x(times[index]!)}
                cy={y(point.value)}
                r={index === active ? 4.5 : 3}
                fill={worrying ? "var(--critical)" : flag ? "var(--watch)" : "white"}
                stroke={worrying ? "var(--critical)" : LINE_COLOR}
                strokeWidth="1.5"
              />
            </g>
          );
        })}
      </svg>
      {range && <p className="mt-1 text-[11px] leading-snug text-ink-faint">{range.label}</p>}
    </figure>
  );
}

function yearBoundaries(t0: number, t1: number): { at: number; label: string }[] {
  const start = new Date(t0).getUTCFullYear();
  const end = new Date(t1).getUTCFullYear();
  const years: { at: number; label: string }[] = [];
  for (let year = start; year <= end; year += 1) {
    const at = Date.UTC(year, 0, 1);
    if (at >= t0 && at <= t1) years.push({ at, label: String(year) });
  }
  if (years.length === 0) years.push({ at: t0, label: formatMonth(t0) });
  return years.length > 6 ? years.filter((_, index) => index % 2 === 0) : years;
}
