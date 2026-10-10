"use client";

import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import type { ProposedAction } from "@/lib/types";
import { Button } from "@/components/ui/button";

const kindLabel: Record<ProposedAction["payload"]["kind"], string> = {
  search: "Search",
  open_tab: "Open tab",
  chart_change: "Chart change",
};

export function ActionCard({ action, detailed = false }: { action: ProposedAction; detailed?: boolean }) {
  const approve = useStore((s) => s.approve);
  const reject = useStore((s) => s.reject);
  const patientName = useStore((s) => s.patients[action.patientId]?.name);
  const pending = action.status === "pending";
  const { payload } = action;

  return (
    <article
      className={cn(
        "rounded-lg px-4 py-3.5 transition-colors",
        pending ? "border border-dashed border-jade-600/45 bg-white" : "border border-hairline bg-transparent",
        action.status === "rejected" && "opacity-55",
      )}
    >
      <div className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.12em] uppercase">
        <span className={pending ? "text-jade-700" : "text-ink-faint"}>{kindLabel[payload.kind]}</span>
        {detailed && <span className="font-normal tracking-normal normal-case text-ink-faint">· {patientName}</span>}
        {!pending && (
          <span className="ml-auto flex items-center gap-1 font-normal tracking-normal normal-case text-ink-faint">
            {action.status === "approved" ? <Check className="size-3.5 text-jade-600" /> : <X className="size-3.5" />}
            {action.status === "approved" ? "Approved" : "Rejected"}
          </span>
        )}
      </div>

      <h3 className={cn("mt-1.5 font-sans text-[15px] font-semibold text-ink", action.status === "rejected" && "line-through")}>
        {action.title}
      </h3>

      {payload.kind === "search" ? (
        <div className="mt-2 space-y-1.5 text-[13px]">
          <p className="text-ink-soft">{payload.corpus}</p>
          <p className="border-l-2 border-hairline-strong pl-3 text-ink">{payload.query}</p>
          <p className="text-ink-faint">Only this de-identified query is sent. No name, MRN, or dates.</p>
        </div>
      ) : action.before || action.after ? (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
          {action.before && (
            <>
              <dt className="text-ink-faint">Before</dt>
              <dd className="text-ink-soft">{action.before}</dd>
            </>
          )}
          {action.after && (
            <>
              <dt className="text-ink-faint">After</dt>
              <dd className="text-ink">{action.after}</dd>
            </>
          )}
        </dl>
      ) : (
        <p className="mt-1 text-[13px] text-ink-soft">{action.detail}</p>
      )}

      {(detailed || action.confidence || action.citations?.length) && (
        <p className="mt-2.5 text-[12px] leading-relaxed text-ink-faint">
          {[action.source, action.confidence, ...(action.citations ?? [])].filter(Boolean).join(" · ")}
        </p>
      )}

      {pending && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" className="rounded-full px-3.5" onClick={() => approve(action.id)}>
            Approve
          </Button>
          <Button size="sm" variant="ghost" className="rounded-full px-3 text-ink-soft" onClick={() => reject(action.id)}>
            Reject
          </Button>
        </div>
      )}
    </article>
  );
}
