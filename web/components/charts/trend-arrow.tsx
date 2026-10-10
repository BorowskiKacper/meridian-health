import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { isConcerning, referenceFor } from "@/lib/reference";
import type { Trend } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Direction of the last two results, coloured by whether the move is the worrying one. */
export function TrendArrow({ trend, className }: { trend: Trend; className?: string }) {
  const points = trend.points;
  if (points.length < 2) return <span className={cn("inline-block size-3.5", className)} aria-hidden />;
  const previous = points.at(-2)!.value;
  const last = points.at(-1)!.value;
  const range = referenceFor(trend.name);
  const tolerance = range?.high !== undefined && range.low !== undefined ? (range.high - range.low) * 0.03 : Math.abs(last) * 0.02;
  const delta = last - previous;
  const flat = Math.abs(delta) <= tolerance;
  const concerning = isConcerning(trend.name, last);
  const Icon = flat ? ArrowRight : delta > 0 ? ArrowUpRight : ArrowDownRight;
  const label = flat ? "stable" : delta > 0 ? "rising" : "falling";
  return (
    <Icon
      aria-label={`${trend.name} ${label}`}
      className={cn("size-3.5 shrink-0", concerning ? "text-critical" : flat ? "text-ink-faint" : "text-jade-600", className)}
    />
  );
}
