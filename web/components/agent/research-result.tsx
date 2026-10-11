"use client";

import { ArrowUpRight } from "lucide-react";
import { useStore } from "@/lib/store";
import type { Citation, ResearchResult as Result, TabKind } from "@/lib/types";

function externalUrl(locator?: string) {
  if (!locator) return undefined;
  try {
    const url = new URL(locator);
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined;
  } catch { return undefined; }
}

function chartTab(locator?: string): TabKind | undefined {
  const kind = locator?.split(":")[0];
  return ({ condition: "problems", medication: "medications", observation: "vitals", note: "timeline", encounter: "timeline", family_history: "history" } as Record<string, TabKind>)[kind ?? ""];
}

function FindingPassage({ citation }: { citation: Citation }) {
  let record: Record<string, unknown> | undefined;
  if (citation.tier === "chart") {
    try {
      const parsed = JSON.parse(citation.passage);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) record = parsed;
    } catch { /* Narrative chart excerpts remain readable as text. */ }
  }
  const fields = ["name", "value", "unit", "status", "dose", "route", "frequency", "relationship", "condition", "age_at_diagnosis", "observed_at", "onset_date", "start_date", "occurred_at", "summary"];
  const rows = record ? fields.filter((key) => record[key] !== undefined && record[key] !== null) : [];
  if (record && rows.length) return <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12px] leading-relaxed">{rows.map((key) => <div key={key} className="contents"><dt className="text-ink-faint">{key.replaceAll("_", " ")}</dt><dd className="break-words text-ink">{String(record[key])}</dd></div>)}</dl>;
  return citation.passage ? <blockquote className="mt-3 whitespace-pre-wrap break-words border-l-2 border-jade-300 pl-3 text-[13px] leading-relaxed text-ink-soft">{citation.passage}</blockquote> : null;
}

function Source({ citation, patientId }: { citation: Citation; patientId: string | null }) {
  const openTab = useStore((s) => s.openTab);
  const url = externalUrl(citation.locator);
  const tab = chartTab(citation.locator);
  return <details className="border-t border-hairline py-3 first:border-t-0">
    <summary className="cursor-pointer text-[13px] font-medium text-ink">{citation.source}</summary>
    <FindingPassage citation={citation} />
    {url && <a href={url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-[12px] font-medium text-jade-700">Open source <ArrowUpRight className="size-3" /></a>}
    {!url && tab && patientId && <button type="button" onClick={() => openTab(tab, patientId)} className="mt-3 inline-flex items-center gap-1 text-[12px] font-medium text-jade-700">View in chart <ArrowUpRight className="size-3" /></button>}
  </details>;
}

export function ResearchResult({ result, compact = false }: { result: Result; compact?: boolean }) {
  const patientId = result.patientId;
  const openTab = useStore((s) => s.openTab);
  const findings = result.patientId ? result.citations.filter((c) => c.tier === "chart") : [];
  const sources = result.citations.filter((c) => c.tier !== "chart");
  return <div className={compact ? "agent-card mt-3 rounded-lg border border-hairline bg-clinical-surface px-4 py-4" : "mt-7 max-w-3xl"}>
    {result.sections?.length ? <div className="space-y-5">{result.sections.map((section, index) => <section key={`${section.title}-${index}`}>
      <h3 className="text-[12px] font-semibold text-jade-800">{section.title}</h3>
      <p className="mt-1.5 whitespace-pre-wrap break-words text-[14px] leading-relaxed text-ink">{section.text}</p>
      {section.source_ids?.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{section.source_ids.map((id) => {
        const citation = result.citations.find((c) => c.id === id);
        if (!citation) return null;
        const url = externalUrl(citation.locator);
        const tab = chartTab(citation.locator);
        const className = "text-left text-[11px] text-jade-700 underline decoration-jade-300 underline-offset-2";
        return url ? <a key={id} href={url} target="_blank" rel="noopener noreferrer" className={className}>{citation.source}</a> : tab && patientId ? <button key={id} type="button" className={className} onClick={() => openTab(tab, patientId)}>{citation.source}</button> : <span key={id} className="text-[11px] text-ink-soft">{citation.source}</span>;
      })}</div>}
    </section>)}</div> : <p className="whitespace-pre-wrap break-words text-[14px] leading-relaxed text-ink">{result.answer || "No supported answer was found for this question."}</p>}
    {findings.length > 0 && <details className="mt-5 rounded-md border border-jade-300 bg-jade-100 px-3 py-3">
      <summary className="cursor-pointer text-[12px] font-semibold text-jade-900">Findings used <span className="ml-1 font-normal text-jade-700">{findings.length}</span></summary>
      <div className="mt-2">{findings.map((citation, index) => <Source key={citation.id ?? index} citation={citation} patientId={result.patientId} />)}</div>
    </details>}
    {sources.length > 0 && <div className="mt-5 border-t border-hairline pt-3">
      <h3 className="mb-1 text-[12px] font-semibold text-jade-800">Sources</h3>
      {sources.map((citation, index) => <Source key={citation.id ?? index} citation={citation} patientId={result.patientId} />)}
    </div>}
    {patientId && result.answer.trim() && <AddToPlan result={result} />}
    {compact && patientId && <button type="button" onClick={() => openTab("research", patientId, result.id)} className="mt-5 inline-flex items-center gap-1 text-[12px] font-medium text-jade-700">Expand research <ArrowUpRight className="size-3.5" /></button>}
  </div>;
}

function AddToPlan({ result }: { result: Result }) {
  const addToPlan = useStore((s) => s.addToPlan);
  const plan = result.plan;
  if (plan?.status === "added") return <p role="status" className="mt-5 text-[13px] text-jade-700">{plan.message}</p>;
  return <div className="mt-5">
    <button type="button" disabled={plan?.status === "saving"} onClick={() => void addToPlan(result.id)} className="rounded-md border border-hairline-strong px-3 py-2 text-[13px] font-medium text-jade-700 hover:bg-jade-50 disabled:opacity-50">{plan?.status === "saving" ? "Adding…" : "Add to plan"}</button>
    {plan?.status === "error" && <p role="alert" className="mt-2 text-[13px] text-critical">{plan.message}</p>}
  </div>;
}
