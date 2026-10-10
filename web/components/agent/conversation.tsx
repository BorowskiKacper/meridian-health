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

const starters: Record<string, string[]> = {
  nora: [
    "Are her screenings up to date?",
    "Should she start a statin given her history?",
    "LDL is 190. Her father had an MI at 55. Start lisinopril 10 mg.",
    "Open the timeline",
  ],
  marcus: [
    "Should we add an SGLT2 inhibitor given his kidneys?",
    "Is he due for any screenings?",
    "Open the reminders",
  ],
};

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
  const column = wide ? "mx-auto w-full max-w-3xl px-8" : "px-6";

  return (
    <div className="flex h-full flex-col">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        {conversation.messages.length === 0 ? (
          <div className={cn(column, "flex min-h-full flex-col justify-end pb-6")}>
            <p className="eyebrow">{patient.mrn}</p>
            <h2 className={cn("mt-3 leading-tight", wide ? "text-[34px]" : "text-[26px]")}>
              What do you need for {patient.name.split(" ")[0]}?
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">
              Dictate a change or ask a question. Searches, new tabs, and chart changes wait for your approval.
            </p>
            <ul className="mt-6 divide-y divide-hairline border-y border-hairline">
              {(starters[patient.id] ?? []).map((starter) => (
                <li key={starter}>
                  <button
                    type="button"
                    onClick={() => {
                      activate(conversation.id);
                      send(starter);
                    }}
                    className="group flex w-full items-center justify-between gap-4 py-3 text-left text-sm text-ink-soft hover:text-ink"
                  >
                    {starter}
                    <ArrowUpRight className="size-4 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
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
    <div className="ml-auto w-fit max-w-[85%] rounded-2xl bg-ivory-deep px-4 py-2.5 text-[14px] leading-relaxed text-ink">
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
      <p className="mt-1.5 text-[14px] leading-relaxed text-ink">{message.text}</p>
      {message.researchId && <ResearchBlock researchId={message.researchId} />}
      {actions.length > 0 && (
        <div className="mt-4 space-y-2.5">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
          {pendingCount > 1 && (
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
    <div className="flex items-center gap-2 text-[12px] text-ink-faint">
      <span className="font-semibold tracking-[0.12em] text-jade-700 uppercase">{routeLabel[route]}</span>
      <span>{message.routedBy === "manual" ? "chosen by you" : "routed automatically"}</span>
      {canReroute && (
        <DropdownMenu>
          <DropdownMenuTrigger className="ml-1 flex items-center gap-0.5 rounded px-1 outline-none hover:bg-ivory-deep hover:text-ink">
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
    <div className="mt-4 rounded-lg border border-hairline bg-white px-4 py-3.5">
      <p className="text-[12px] text-ink-faint italic">{result.basis}</p>
      <p className="mt-2 font-serif text-[16px] leading-relaxed text-jade-900">{result.answer}</p>
      {result.citations.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {result.citations.map((citation, index) => (
            <li key={citation.source} className="flex gap-2 text-[12px] leading-snug text-ink-soft">
              <span className="numeric text-jade-700">{index + 1}</span>
              {citation.source}
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
