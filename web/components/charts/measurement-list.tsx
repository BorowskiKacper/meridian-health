"use client";

import { ChevronDown } from "lucide-react";
import { formatDate } from "@/lib/data";
import { bloodPressure, recordedPoints } from "@/lib/clinical";
import type { Trend } from "@/lib/types";
import { ObservationChart } from "./observation-chart";

/** One dated value per series; deeper trend and provenance are available on demand. */
/** Latest minus previous recorded value, coloured green when it rose and red when it fell. */
function Change({ trend }: { trend: Trend }) {
  const [previous, latest] = trend.points.slice(-2);
  // A blood-pressure half with no earlier reading still needs a placeholder, or "/+4" reads as broken.
  if (!previous || !latest) return <span className="text-ink-faint">–</span>;
  const delta = Math.round((latest.value - previous.value) * 10) / 10;
  return <span className={delta > 0 ? "text-jade-700" : delta < 0 ? "text-critical" : "text-ink-soft"}>{delta > 0 ? "+" : ""}{delta}</span>;
}

const CHANGE_SHOWN = /blood pressure|weight|heart rate|^pulse$/i;

export function MeasurementList({ series, markers = [], limit, showChange = false, expected = [] }: { series: Trend[]; markers?: { at: string; label: string }[]; limit?: number; showChange?: boolean; /** Rows always listed, as "Not recorded" when no series matches. */ expected?: { name: string; match: RegExp }[] }) {
  const recorded = series.map((trend) => ({ ...trend, points: recordedPoints(trend) })).filter((trend) => trend.points.length);
  const bp = bloodPressure(recorded);
  // Pair only readings collected at the same time with the same recorded unit.
  const pair = bp.length === 2 && bp[0]!.unit === bp[1]!.unit && Date.parse(bp[0]!.points.at(-1)!.at) === Date.parse(bp[1]!.points.at(-1)!.at);
  const groups = recorded.flatMap((trend) => {
    if (pair && bp.includes(trend)) return trend === bp[0] ? [{ name: "Blood pressure", series: bp }] : [];
    return [{ name: trend.name, series: [trend] }];
  });
  const shown = limit ? groups.slice(0, limit) : groups;
  const missing = expected.filter((row) => !recorded.some((trend) => row.match.test(trend.name)));
  return <div className="divide-y divide-hairline border-y border-hairline">
    {shown.map((group) => {
      const latest = group.series[0]!.points.at(-1)!;
      const value = group.series.map((trend) => trend.points.at(-1)!.value).join("/");
      const unit = group.series[0]!.unit;
      const changes = showChange && CHANGE_SHOWN.test(group.name) && group.series.some((trend) => trend.points.length > 1);
      return <details key={`${group.name}-${unit}`} className="group">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-5 gap-y-2 py-4 [&::-webkit-details-marker]:hidden">
          <span className="min-w-0 flex-1 basis-40 text-[13px] font-medium text-ink">{group.name}</span>
          <span className="text-right"><span className="block text-[14px] text-ink"><strong className="numeric font-semibold">{value}</strong> <span className="text-[12px] text-ink-soft">{unit || "Unit not recorded"}</span></span>{changes && <span className="numeric mt-1 block text-[12px] font-medium">{group.series.map((trend, index) => <span key={trend.name}>{index > 0 && "/"}<Change trend={trend} /></span>)} <span className="font-normal text-ink-faint">since last</span></span>}<span className="mt-1 block text-[11px] text-ink-faint">{formatDate(latest.at)}</span></span>
          <ChevronDown aria-hidden className="size-3.5 shrink-0 text-ink-faint transition-transform group-open:rotate-180" />
        </summary>
        <div className="pb-5"><ObservationChart title={group.name} series={group.series} markers={markers} compact hideLatest /></div>
      </details>;
    })}
    {missing.map((row) => <div key={row.name} className="flex flex-wrap items-center gap-x-5 gap-y-2 py-4 pr-[1.125rem]"><span className="min-w-0 flex-1 basis-40 text-[13px] font-medium text-ink">{row.name}</span><span className="text-[13px] text-ink-faint">Not recorded</span></div>)}
    {!shown.length && !missing.length && <p className="py-5 text-[13px] text-ink-soft">No measurements recorded.</p>}
  </div>;
}
