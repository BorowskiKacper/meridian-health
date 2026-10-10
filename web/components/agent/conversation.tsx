"use client";

import { useEffect, useRef } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import type { Agent, Message, Route } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ActionCard } from "./action-card";
import { Composer } from "./composer";

export const routeLabel: Record<Route, string> = {
  chart: "Chart",
  research: "Ask",
  screening: "Screening",
  navigate: "Workspace",
};

const starters = ["Are screenings up to date?", "What is on the chart?", "Open the timeline"];

export function ConversationView({ conversationId, wide = false }: { conversationId: string; wide?: boolean }) {
  const conversation = useStore((s) => s.conversations.find((c) => c.id === conversationId));
  const patient = useStore((s) => (conversation ? s.patients[conversation.patientId] : undefined));
  const send = useStore((s) => s.send);
  const activate = useStore((s) => s.activateConversation);
  const scroller = useRef<HTMLDivElement>(null);
  const count = conversation?.messages.length ?? 0;
  const lastText = conversation?.messages.at(-1)?.text;

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [count, lastText]);

  if (!conversation || !patient) return null;
  const column = wide ? "mx-auto w-full max-w-3xl px-6" : "px-6";

  return (
    <div className="flex h-full flex-col">
      <div className={cn(column, "agent-rule flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-hairline py-4")}>
        <span className="agent-accent text-[12px] font-semibold text-jade-700">Assistant</span>
        <span className="agent-dim text-[12px] text-ink-soft">{patient.name} · {patient.mrn}</span>
      </div>
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        {conversation.messages.length === 0 ? (
          <div className={cn(column, "flex min-h-full flex-col py-8")}>
            <h2 className="text-[25px] leading-tight">
              How can I help with {patient.name.split(" ")[0]}’s care?
            </h2>
            <p className="agent-dim mt-3 text-sm leading-relaxed text-ink-soft">
              Review the chart, ask a question, or draft a change. Review proposed chart changes before approving them.
            </p>
            <ul className="agent-rule mt-6 divide-y divide-hairline border-y border-hairline">
              {starters.map((starter) => (
                <li key={starter}>
                  <button
                    type="button"
                    onClick={() => {
                      activate(conversation.id);
                      send(starter);
                    }}
                    className="agent-dim group flex w-full items-center justify-between gap-4 py-3 text-left text-sm text-ink-soft hover:text-ink"
                  >
                    {starter}
                    <ArrowUpRight className="size-3.5 shrink-0 opacity-60 group-hover:opacity-100" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className={cn(column, "space-y-7 py-6")}>
            {conversation.messages.map((message) => (
              <li key={message.id}>
                {message.role === "doctor" ? <DoctorMessage message={message} /> : <AgentMessage message={message} />}
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className={cn(column, "shrink-0 pb-5")}>
        <Composer conversationId={conversation.id} />
      </div>
    </div>
  );
}

function DoctorMessage({ message }: { message: Message }) {
  return (
    <div className="agent-bubble ml-auto w-fit max-w-[85%] rounded-lg bg-ivory-deep px-4 py-2.5 text-[14px] leading-relaxed text-ink">
      {message.text}
    </div>
  );
}

function AgentMessage({ message }: { message: Message }) {
  const actions = useStore(useShallow((s) => s.actions.filter((a) => a.messageId === message.id)));
  const approveMessage = useStore((s) => s.approveMessage);
  const pendingCount = actions.filter((a) => a.status === "pending").length;

  if (message.pending) {
    return (
      <div className="flex items-center gap-1.5 py-1" aria-label="Working">
        {[0, 1, 2].map((i) => (
          <span key={i} className="size-1.5 animate-pulse rounded-full bg-jade-600/60" style={{ animationDelay: `${i * 160}ms` }} />
        ))}
      </div>
    );
  }

  return (
    <div>
      {message.route && <RouteLine message={message} />}
      <p className="agent-text mt-1.5 text-[14px] leading-relaxed text-ink">{message.text}</p>
      {message.researchId && <ResearchBlock researchId={message.researchId} />}
      {actions.length > 0 && (
        <div className="mt-4 space-y-2.5">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
          {pendingCount > 1 && actions.every((a) => a.payload.kind !== "chart_change") && (
            <Button size="sm" variant="outline" className="rounded-full px-3.5" onClick={() => approveMessage(message.id)}>
              Approve all {pendingCount}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function RouteLine({ message }: { message: Message }) {
  const reroute = useStore((s) => s.reroute);
  const route = message.route!;
  const others = (["chart", "research", "screening"] as Agent[]).filter((r) => r !== route);
  const canReroute = Boolean(message.requestText);

  return (
    <div className="agent-dim flex items-center gap-2 text-[12px] text-ink-faint">
      <span className="agent-accent font-semibold tracking-[0.12em] text-jade-700 uppercase">{routeLabel[route]}</span>
      <span>{message.routedBy === "manual" ? "chosen by you" : "routed automatically"}</span>
      {canReroute && (
        <DropdownMenu>
          <DropdownMenuTrigger className="agent-hover ml-1 flex items-center gap-0.5 rounded px-1 outline-none hover:bg-ivory-deep hover:text-ink">
            Re-route <ChevronDown className="size-3" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-60">
            <DropdownMenuGroup>
              <DropdownMenuLabel>Send the same request to</DropdownMenuLabel>
              {others.map((r) => (
                <DropdownMenuItem key={r} onClick={() => reroute(message.id, r)}>
                  {routeLabel[r]}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <p className="px-1.5 pt-1 pb-1.5 text-[11px] leading-snug text-ink-faint">Pending items from this reply are discarded.</p>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}

function ResearchBlock({ researchId }: { researchId: string }) {
  const result = useStore((s) => s.research[researchId]);
  const openTab = useStore((s) => s.openTab);
  if (!result) return null;
  return (
    <div className="agent-card mt-4 min-w-0 rounded-lg border border-hairline bg-white px-4 py-3.5">
      <p className="text-[12px] text-ink-faint italic">{result.basis}</p>
      <p className="mt-2 break-words text-[14px] leading-relaxed text-jade-900">{result.answer}</p>
      {result.citations.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {result.citations.map((citation, index) => (
            <li key={citation.source} className="flex gap-2 text-[12px] leading-snug text-ink-soft">
              <span className="numeric shrink-0 text-jade-700">{index + 1}</span>
              <span className="min-w-0 break-words">{citation.source}</span>
            </li>
          ))}
        </ol>
      )}
      <button
        type="button"
        onClick={() => openTab("research", result.patientId, result.id)}
        className="mt-3 flex items-center gap-1 text-[12px] font-semibold text-jade-700 hover:text-jade-900"
      >
        Open in a tab <ArrowUpRight className="size-3.5" />
      </button>
    </div>
  );
}
