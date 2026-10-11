"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { isVital, recordedPoints, sourceLabel } from "@/lib/clinical";
import { formatDate, firstName } from "@/lib/data";
import { Page, PageHeader } from "@/components/system/primitives";
import { MeasurementList } from "@/components/charts/measurement-list";
import { entryButton, entryInput } from "@/components/chart-entry/entry-form";

export function LabTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const extractLab = useStore((s) => s.extractLab);
  const uploaded = useStore((s) => s.uploadedLabs[patientId]);
  const openTab = useStore((s) => s.openTab);
  const [query, setQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  if (!patient) return null;
  const labs = patient.trends.filter((t) => !isVital(t));
  const shown = labs.filter((t) => `${t.name} ${t.unit}`.toLowerCase().includes(query.toLowerCase()));
  const results = shown.flatMap((t) => recordedPoints(t).map((p) => ({ ...p, name: t.name, unit: t.unit }))).sort((a, b) => b.at.localeCompare(a.at));
  return <Page wide>
    <PageHeader eyebrow="Recorded clinical findings" title={`${firstName(patient.name)}’s Diagnostics`}>Results, collection dates, and original sources. Expand a test to inspect its trend and exact values.</PageHeader>
    <div className="mt-6 flex flex-wrap items-end justify-between gap-4 border-y border-hairline py-4"><label className="min-w-0 flex-1 basis-64 text-[12px] text-ink-soft">Find a test<input className={entryInput} type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search recorded results" /></label><span className="pb-2 text-[12px] text-ink-faint">{labs.length} recorded test{labs.length === 1 ? "" : "s"} · {results.length} result{results.length === 1 ? "" : "s"} in this view</span></div>
    <section className="mt-6"><div className="mb-3 flex flex-wrap justify-between gap-3"><h2 className="font-sans text-[15px] font-semibold">Latest results by test</h2><button type="button" className="text-[12px] text-jade-700 hover:underline" onClick={() => openTab("body", patientId)}>View by anatomy →</button></div><p className="mb-4 text-[12px] leading-relaxed text-ink-faint">Reference intervals, specimen details, and lab-issued abnormal or critical flags are not supplied. No normality or urgency is inferred from these values.</p>{shown.length ? <MeasurementList series={shown} /> : <p className="border-y border-hairline py-5 text-sm text-ink-soft">{query ? "No recorded tests match this search." : "No diagnostic measurements recorded."}</p>}</section>
    <details className="mt-6"><summary className="cursor-pointer text-[13px] font-medium text-jade-700">Result history & provenance · {results.length}</summary><div className="mt-4 overflow-x-auto" role="region" aria-label="Diagnostic result history" tabIndex={0}><table className="clinical-table min-w-[640px]"><thead><tr>{["Collected", "Test", "Result", "Source", "Document reference"].map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{results.map((r, i) => <tr key={r.id || `${r.name}-${r.at}-${i}`}><td><time dateTime={r.at}>{formatDate(r.at)}</time></td><td>{r.name}</td><td className="numeric"><strong>{r.value}</strong> {r.unit || "Unit not recorded"}</td><td>{sourceLabel(r.source)}</td><td className="max-w-48 break-all text-[12px] text-ink-soft">{r.documentId || "Not supplied"}</td></tr>)}</tbody></table></div>{!results.length && <p className="mt-3 text-sm text-ink-soft">No result history in this view.</p>}</details>
    <section className="mt-8 border-t border-hairline pt-6"><h2 className="font-sans text-[15px] font-semibold">Upload a clinical document</h2><p className="mt-2 text-[13px] leading-relaxed text-ink-soft">Upload a PDF, image, TXT, or CSV lab report. Extracted numeric values become proposals for review; only approved values enter the recorded chart. Reports must include collection dates.</p><form className="mt-4" onSubmit={async (e) => { e.preventDefault(); if (!file || busy) return; setBusy(true); setMessage(""); setError(false); try { const result = await extractLab(patientId, file); if (!result) { setError(true); setMessage("Upload could not be confirmed. Check before retrying."); return; } setMessage(result.suggestions.length ? `Document stored. ${result.suggestions.length} proposed results await review in Approvals.` : "Document stored. No dated numeric values could be extracted. Review the report for collection dates, readable values, and units."); setFile(null); } catch { setError(true); setMessage("Upload could not be confirmed. Check before retrying."); } finally { setBusy(false); } }}><label className="block text-[13px] text-ink-soft" htmlFor={`document-${patientId}`}>Choose a report</label><input key={uploaded} id={`document-${patientId}`} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv" disabled={busy} className="mt-3 block max-w-full text-[13px] text-ink-soft file:mr-3 file:rounded-md file:border file:border-hairline-strong file:bg-ivory file:px-3 file:py-2 file:text-jade-700" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setMessage(""); }} /><button className={`${entryButton} mt-4`} disabled={!file || busy}>{busy ? "Uploading…" : "Upload document"}</button></form>{message && <p role={error ? "alert" : "status"} className={`mt-4 text-[13px] ${error ? "text-critical" : "text-jade-700"}`}>{message}</p>}{uploaded && <p className="mt-3 break-all text-[12px] text-ink-faint">Latest upload in this session: {uploaded}. Original document viewing is not connected.</p>}</section>
    <details className="mt-8 border-t border-hairline pt-4 text-[13px]"><summary className="cursor-pointer font-medium text-ink-soft">Imaging, pathology & other diagnostic reports</summary><p className="mt-3 leading-relaxed text-ink-soft">Imaging impressions and PACS viewers, pathology and microbiology reports, and genomic findings are not connected. Numeric lab measurements can be extracted for review. Imaging impressions, pathology narratives, and genomic interpretations require dedicated report integrations.</p></details>
  </Page>;
}
