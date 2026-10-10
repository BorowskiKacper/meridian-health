import type { Trend } from "@/lib/types";
import { ObservationChart } from "./observation-chart";

/** Recorded values without turning generic display thresholds into clinical flags. */
export function TrendChart({ trend, markers = [], className }: { trend: Trend; markers?: { at: string; label: string }[]; className?: string }) {
  return <div className={className}><ObservationChart title={trend.name} series={[trend]} markers={markers} /></div>;
}
