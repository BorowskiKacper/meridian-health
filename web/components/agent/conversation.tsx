"use client";

import { useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import type { Message, Route } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ActionCard } from "./action-card";
import { Composer } from "./composer";
import { ResearchResult } from "./research-result";
import { clarifyWorkspace } from '@/lib/workspace-api';

export const routeLabel: Record<Route, string> = {
  chart: "Proposed chart changes",
  research: "Patient research",
  screening: "Screening",
  navigate: "Workspace",
};



export function ConversationView({ conversationId, wide = false }: { conversationId: string; wide?: boolean }) {
  const conversation = useStore((s) => s.conversations.find((c) => c.id === conversationId));
  const requestMode = useStore((s) => s.requestModes[conversationId]);
  const patient = useStore((s) => (conversation?.patientId ? s.patients[conversation.patientId] : undefined));
  const capabilities = useStore((s) => s.capabilities);
  const scroller = useRef<HTMLDivElement>(null);
  const count = conversation?.messages.length ?? 0;
  const lastText = conversation?.messages.at(-1)?.text;

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [count, lastText]);

  if (!conversation || (conversation.patientId !== null && !patient)) return null;
  const column = wide ? "mx-auto w-full max-w-3xl px-6" : "px-6";

  return (
    <div className="flex h-full flex-col">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        {conversation.messages.length === 0 ? (
          <div className={cn(column, "flex min-h-full flex-col py-8")}>
            <h2 className="text-[22px] leading-tight">What would you like to work on?</h2>
            <p className="agent-dim mt-3 text-sm leading-relaxed">{conversation.patientId === null ? "Ask about clinical evidence, guidelines, or general medical questions. No patient chart is attached." : "Ask a patient-specific question, document findings, or review screening needs."}</p>
          </div>
        ) : (
          <ol className={cn(column, "space-y-7 py-6")}>
            {conversation.messages.map((message) => (
              <li key={message.id} data-workspace-reply={message.role === 'agent' && !message.pending ? message.workspaceJobId : undefined}>
                {message.role === "doctor" ? <DoctorMessage message={message} /> : <AgentMessage message={message} mode={requestMode} general={conversation.patientId === null} />}
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className={cn(column, "shrink-0 border-t border-white/15 pt-3 pb-5")}>
        {capabilities?.assistant === false && <p className="agent-dim mb-3 text-[11px] leading-relaxed">The assistant is not configured on the server. Direct chart entry is available.</p>}
        <Composer key={conversation.id} conversationId={conversation.id} />
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

function AgentMessage({ message, mode, general }: { message: Message; mode?: string; general?: boolean }) {
  const actions = useStore(useShallow((s) => s.actions.filter((a) => a.messageId === message.id)));
  const approveMessage = useStore((s) => s.approveMessage);
  const busy = useStore((s) => s.actions.some((a) => a.messageId === message.id && s.approvingIds.includes(a.id)));
  const pendingCount = actions.filter((a) => a.status === "pending").length;

  if (message.pending) {
    return (
      <div className="flex items-center gap-1.5 py-1" role="status">
        <span className="mr-2 text-[12px] text-white/80">{message.route === "research" || mode === "clinical_question" ? "Researching…" : message.route === "chart" || mode === "chart_update" ? "Drafting…" : message.route === "screening" || mode === "check_screenings" ? "Reviewing screenings…" : "Working…"}</span>
        {[0, 1, 2].map((i) => (
          <span key={i} className="agent-working size-1.5 animate-pulse rounded-full bg-jade-600/60" style={{ animationDelay: `${i * 160}ms` }} />
        ))}
      </div>
    );
  }

  return (
    <div>
      {message.route && <RouteLine message={message} general={general} />}
      {!message.researchId && <p role={message.error ? "alert" : undefined} className={cn("agent-text mt-1.5 whitespace-pre-wrap text-[14px] leading-relaxed text-ink", message.error && "rounded-md border border-white/25 p-3")}>{message.text}</p>}
      {message.workspaceJobId && <PatientClarification jobId={message.workspaceJobId} />}
      {message.audioBase64 && <audio controls className="mt-3 h-9 max-w-full" aria-label="Spoken assistant response" src={`data:audio/mpeg;base64,${message.audioBase64}`} />}
      {message.researchId && <ResearchBlock researchId={message.researchId} />}
      {actions.length > 0 && (
        <div className="mt-4 space-y-2.5">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
          {pendingCount > 1 && actions.every((a) => a.payload.kind !== "chart_change") && (
            <Button size="sm" disabled={busy} variant="outline" className="rounded-full px-3.5" onClick={() => approveMessage(message.id)}>
              {busy ? "Approving…" : `Approve all ${pendingCount}`}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function PatientClarification({ jobId }: { jobId: string }) {
  const job = useStore((s) => s.workspaceJobs[jobId]);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  if (job?.status !== 'needs_patient') return null;
  const clarify = async (patientId?: string) => {
    if (busy || (!patientId && !query.trim())) return;
    setBusy(true);
    try { await useStore.getState().syncWorkspaceJob(await clarifyWorkspace(jobId, patientId ? '' : query, patientId)); setQuery(''); }
    catch (error) { useStore.setState({ notice: error instanceof Error ? error.message : 'Patient clarification could not be confirmed.' }); }
    finally { setBusy(false); }
  };
  return <div className="mt-3 flex flex-col gap-2">
    {job.candidates?.map((patient) => <button type="button" disabled={busy} key={patient.id} className="rounded-md border border-white/20 px-3 py-2 text-left text-[13px] text-ivory hover:bg-white/10 disabled:opacity-50" onClick={() => void clarify(patient.id)}>{patient.display_name} · DOB {patient.date_of_birth}</button>)}
    <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); void clarify(); }}>
      <input aria-label="Patient name or record ID for this request" placeholder="Patient name or record ID" maxLength={200} value={query} disabled={busy} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 rounded-md border border-white/20 bg-white/10 px-3 py-2 text-[13px] text-ivory placeholder:text-ivory/60" />
      <button type="submit" disabled={busy || !query.trim()} className="rounded-md border border-white/20 px-3 py-2 text-[13px] text-ivory hover:bg-white/10 disabled:opacity-50">{busy ? 'Finding…' : 'Use patient'}</button>
    </form>
  </div>;
}

function RouteLine({ message, general }: { message: Message; general?: boolean }) {
  return <div className="agent-dim flex items-center gap-2 text-[12px]">
    <span className="agent-accent font-semibold tracking-[0.12em] uppercase">{general ? "Research" : routeLabel[message.route!]}</span>
  </div>;
}

function ResearchBlock({ researchId }: { researchId: string }) {
  const result = useStore((s) => s.research[researchId]);
  if (!result) return null;
  return <ResearchResult result={result} compact />;
}
