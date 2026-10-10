"use client";

import { Check, LoaderCircle, X } from "lucide-react";
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
  const approving = useStore((s) => s.approvingIds.includes(action.id));
  const approvalError = useStore((s) => s.approvalErrors[action.id]);
  const busy = useStore((s) => s.actions.some((a) => a.patientId === action.patientId && s.approvingIds.includes(a.id)));
  const pending = action.status === "pending";
  const { payload } = action;

  return (
    <article
      aria-busy={approving}
      className={cn(
        "agent-card min-w-0 rounded-lg transition-colors",
        detailed ? "px-5 py-5" : "px-4 py-3.5",
        pending ? "border border-dashed border-jade-600/45 bg-white" : "border border-hairline bg-transparent",
        action.status === "rejected" && "opacity-55",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[11px] font-semibold tracking-[0.12em] uppercase">
        <span className={cn("agent-accent", pending ? "text-jade-700" : "text-ink-faint")}>{kindLabel[payload.kind]}</span>
        {detailed && <span className="font-normal tracking-normal normal-case text-ink-faint">· {patientName}</span>}
        {!pending && (
          <span className="ml-auto flex items-center gap-1 font-normal tracking-normal normal-case text-ink-faint">
            {action.status === "approved" ? <Check className="size-3.5 text-jade-600" /> : <X className="size-3.5" />}
            {action.status === "approved" ? "Approved" : "Rejected"}
          </span>
        )}
      </div>

      <h3 className={cn("agent-text mt-3 break-words font-sans text-[15px] font-semibold text-ink", action.status === "rejected" && "line-through")}>
        {action.title}
      </h3>

      {payload.kind === "search" ? (
        <div className="mt-2 space-y-1.5 text-[13px]">
          <p className="text-ink-soft">{payload.corpus}</p>
          <p className="border-l-2 border-hairline-strong pl-3 text-ink">{payload.query}</p>
          <p className="text-ink-faint">Only this de-identified query is sent. No name, MRN, or dates.</p>
        </div>
      ) : action.before || action.after ? (
        <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 text-[13px] leading-relaxed">
          {action.before && (
            <>
              <dt className="text-ink-faint">Before</dt>
              <dd className="min-w-0 break-words text-ink-soft">{action.before}</dd>
            </>
          )}
          {action.after && (
            <>
              <dt className="text-ink-faint">After</dt>
              <dd className="min-w-0 break-words text-ink">{action.after}</dd>
            </>
          )}
        </dl>
      ) : (
        <p className="mt-1 text-[13px] text-ink-soft">{action.detail}</p>
      )}

      {(detailed || action.confidence || action.citations?.length) && (
        <p className="mt-4 break-words text-[12px] leading-relaxed text-ink-faint">
          {[action.source, action.confidence, ...(action.citations ?? [])].filter(Boolean).join(" · ")}
        </p>
      )}

      {approvalError && <p role="alert" className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-[13px] leading-relaxed text-red-900">{approvalError}</p>}

      {pending && (
        <div className="mt-5 flex flex-wrap gap-3">
          <Button size="sm" disabled={busy} className="rounded-md px-3.5" onClick={() => approve(action.id)}>
            {approving && <LoaderCircle aria-hidden className="size-3.5 animate-spin" />}
            <span role="status">{approving ? "Approving…" : "Approve"}</span>
          </Button>
          <Button size="sm" disabled={busy} variant="ghost" className="rounded-md px-3 text-ink-soft" onClick={() => reject(action.id)}>
            Reject
          </Button>
        </div>
      )}
    </article>
  );
}
