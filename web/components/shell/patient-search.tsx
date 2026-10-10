"use client";

import { useEffect, useRef, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Plus, Search, X } from "lucide-react";
import { searchPatients, type PatientSearchRow } from "@/lib/api";
import { formatDate, initials } from "@/lib/data";
import { useStore } from "@/lib/store";

export function PatientSearch({ variant = "plus", patientName }: { variant?: "plus" | "name"; patientName?: string }) {
  const patients = useStore((state) => state.patients);
  const tabs = useStore((state) => state.tabs);
  const openPatient = useStore((state) => state.openPatient);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<{ rows: PatientSearchRow[]; hasMore: boolean; loading: boolean; error: string }>({ rows: [], hasMore: false, loading: false, error: "" });
  const [opening, setOpening] = useState<string | null>(null);
  const [openError, setOpenError] = useState("");
  const [retry, setRetry] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const term = query.trim();

  useEffect(() => {
    if (!open || term.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      searchPatients(term, 20, controller.signal).then((data) => {
        if (!controller.signal.aborted) setResult({ rows: data.patients, hasMore: data.has_more, loading: false, error: "" });
      }).catch(() => {
        if (!controller.signal.aborted) setResult({ rows: [], hasMore: false, loading: false, error: "Patient search could not connect. Try again." });
      });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, term, retry]);

  const recentIds = [...new Set([...tabs].reverse().map((tab) => tab.patientId))].slice(0, 5);
  const recent = recentIds.map((id) => patients[id]).filter(Boolean).map((patient) => ({ id: patient.id, display_name: patient.name, date_of_birth: patient.dob ?? null, sex: patient.sex }));
  const rows = term ? term.length >= 2 ? result.rows : [] : recent;
  const choose = async (patient: PatientSearchRow) => {
    if (opening) return;
    setOpening(patient.id);
    setOpenError("");
    try { await openPatient(patient.id); setOpen(false); }
    catch (error) { setOpenError(error instanceof Error ? error.message : "This chart could not open. Try again."); }
    finally { setOpening(null); }
  };

  return <Dialog.Root open={open} onOpenChange={(next) => {
    if (opening) return;
    setOpen(next);
    if (next) { setQuery(""); setOpenError(""); setResult({ rows: [], hasMore: false, loading: false, error: "" }); }
  }}>
    <Dialog.Trigger aria-label={variant === "plus" ? "Find patient" : "Find another patient"} className={variant === "plus" ? "mb-1.5 grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-ivory-deep hover:text-ink" : "flex max-w-full items-center gap-2 text-left text-[17px] font-semibold text-ink hover:text-jade-700"}>
      {variant === "plus" ? <Plus className="size-4" /> : <><span>{patientName}</span><Search className="size-3.5 shrink-0 text-ink-faint" /></>}
    </Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-[70] bg-ink/25" />
      <Dialog.Popup initialFocus={input} className="fixed top-1/2 left-1/2 z-[80] flex max-h-[calc(100dvh_-_3rem)] w-[calc(100%_-_2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border border-hairline-strong bg-clinical-surface shadow-lg">
        <div className="flex items-start justify-between gap-5 px-5 pt-5">
          <div><Dialog.Title className="font-sans text-[17px] font-semibold">Find a patient</Dialog.Title><Dialog.Description className="mt-1 text-[13px] leading-relaxed text-ink-soft">Search by name, date of birth (YYYY-MM-DD), or record ID.</Dialog.Description></div>
          <Dialog.Close aria-label="Close patient search" disabled={Boolean(opening)} className="grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-jade-50 disabled:opacity-50"><X className="size-4" /></Dialog.Close>
        </div>
        <div className="mx-5 mt-5 flex items-center gap-3 rounded-md border border-hairline-strong px-3 focus-within:border-jade-600"><Search className="size-4 shrink-0 text-ink-faint" /><input ref={input} aria-label="Search patients" placeholder="Name, date of birth, or record ID" maxLength={200} disabled={Boolean(opening)} value={query} onChange={(event) => { setQuery(event.target.value); setOpenError(""); setResult({ rows: [], hasMore: false, loading: event.target.value.trim().length >= 2, error: "" }); }} onKeyDown={(event) => {
          if (event.key === "ArrowDown") { event.preventDefault(); results.current?.querySelector<HTMLButtonElement>("button")?.focus(); }
          if (event.key === "Enter" && rows.length === 1 && !result.loading) { event.preventDefault(); void choose(rows[0]!); }
        }} className="min-w-0 flex-1 bg-transparent py-3 text-[14px] outline-none" /></div>
        <p className="px-5 pt-4 pb-2 text-[12px] text-ink-faint" role="status">{opening ? "Opening patient chart…" : term.length < 2 ? term ? "Enter at least two characters to search." : "Recently opened" : result.loading ? "Searching…" : result.error ? "Search unavailable" : `${rows.length} result${rows.length === 1 ? "" : "s"}${result.hasMore ? " · Refine your search for more matches" : ""}`}</p>
        <div ref={results} className="max-h-80 min-h-24 overflow-y-auto px-2 pb-3">
          {rows.map((patient) => <button key={patient.id} type="button" disabled={Boolean(opening)} onClick={() => void choose(patient)} className="flex w-full items-center gap-3 rounded-md px-3 py-3 text-left hover:bg-jade-50 disabled:opacity-60">
            <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-md bg-jade-100 text-[12px] font-semibold text-jade-900">{initials(patient.display_name)}</span>
            <span className="min-w-0"><span className="block text-[14px] font-semibold text-ink">{patient.display_name}</span><span className="mt-1 block text-[12px] leading-relaxed text-ink-soft">DOB {formatDate(patient.date_of_birth) || "not recorded"} · Record R-{patient.id.replaceAll("-", "").slice(0, 6).toUpperCase()}</span></span>
          </button>)}
          {!rows.length && !result.loading && !result.error && <p className="px-3 py-5 text-[13px] text-ink-soft">{term.length >= 2 ? "No matching patients. Try a different name or identifier." : "Enter a name or identifier to find a patient."}</p>}
          {result.error && <div className="px-3 py-4"><p role="alert" className="text-[13px] text-critical">{result.error}</p><button type="button" className="mt-3 text-[13px] font-medium text-jade-700 hover:underline" onClick={() => { setResult({ ...result, error: "", loading: true }); setRetry(retry + 1); }}>Retry search</button></div>}
          {openError && <p role="alert" className="px-3 py-4 text-[13px] text-critical">{openError}</p>}
        </div>
      </Dialog.Popup>
    </Dialog.Portal>
  </Dialog.Root>;
}
