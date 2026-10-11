"use client";

import { ChevronRight, ShieldAlert } from "lucide-react";
import { formatDate, initials } from "@/lib/data";
import { allergySummary, currentAllergies } from "@/lib/clinical";
import { useStore } from "@/lib/store";
import type { WorkTab } from "@/lib/types";
import { PatientSearch } from "./patient-search";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

const chartSectionClass = "cursor-pointer rounded-md px-2.5 py-1.5 outline-none transition-colors duration-150 hover:bg-jade-100 hover:text-jade-900 focus-visible:bg-jade-100 focus-visible:text-jade-900 focus-visible:ring-2 focus-visible:ring-jade-600 active:bg-jade-200";

export function PatientBanner({ tab, compact = false }: { tab: WorkTab; compact?: boolean }) {
  const patients = useStore((s) => s.patients);
  const patient = patients[tab.patientId];
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;
  const problems = patient.problems.filter((p) => p.status !== "resolved").length;
  const meds = patient.medications.filter((m) => m.status === "active").length;
  const severe = currentAllergies(patient.allergies).some((a) => ["severe", "anaphylaxis"].includes(a.severity));

  return (
    <div className="shrink-0 border-b border-hairline bg-ivory text-[13px]">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-3 @min-[600px]:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-md bg-jade-100 font-semibold text-jade-900">{initials(patient.name)}</span>
          <div className="min-w-0">
            <PatientSearch variant="name" patientName={patient.name} />
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">DOB {patient.dob ? formatDate(patient.dob) : "not recorded"} · {patient.age} years · <span className="capitalize">{patient.sex}</span></p>
            <p className="text-[11px] text-ink-faint" title={`Full record ID: ${patient.id}`}>Record {patient.mrn}</p>
          </div>
        </div>
        <button type="button" onClick={() => openTab("allergies", patient.id)} aria-label="Review allergies"
          className={`flex max-w-sm items-start gap-2.5 rounded-md border px-3 py-2 text-left hover:bg-white ${severe ? "border-critical/30 bg-critical/5" : "border-hairline"}`}>
          <ShieldAlert className={`mt-0.5 size-4 shrink-0 ${severe ? "text-critical" : "text-ink-soft"}`} />
          <span><span className="block text-[11px] font-semibold text-ink-soft">Allergies{severe ? " · Severe reaction recorded" : ""}</span><span className={`mt-0.5 block text-[12px] ${severe ? "text-critical" : "text-ink"}`}>{allergySummary(patient.allergies)}</span>{currentAllergies(patient.allergies).filter((a) => a.category !== "nkda").map((a) => <span key={a.id} className="mt-1 block text-[11px] text-ink-soft">{a.reaction || "Reaction not recorded"} · {a.severity}</span>)}</span>
          <ChevronRight className="mt-1 size-3.5 shrink-0 text-ink-faint" />
        </button>
      </div>
      {!compact && <nav aria-label="Patient chart sections" className="flex flex-wrap items-center gap-x-1 gap-y-1 border-t border-hairline px-5 py-2 text-[12px] text-ink-soft @min-[600px]:px-8">
        <button type="button" onClick={() => openTab("overview", patient.id)} className={chartSectionClass}>Overview</button>
        <button type="button" onClick={() => openTab("problems", patient.id)} className={chartSectionClass}>Problems <span className="numeric font-semibold">{problems}</span></button>
        <button type="button" onClick={() => openTab("medications", patient.id)} className={chartSectionClass}>Medications <span className="numeric font-semibold">{meds}</span></button>
        <button type="button" onClick={() => openTab("vitals", patient.id)} className={chartSectionClass}>Vitals</button>
        <button type="button" onClick={() => openTab("lab", patient.id)} className={chartSectionClass}>Diagnostics</button>
        <button type="button" onClick={() => openTab("visit", patient.id)} className={chartSectionClass}>Visit draft</button>
        <button type="button" onClick={() => openTab("reminders", patient.id)} className={chartSectionClass}>Follow-up</button>
        <DropdownMenu><DropdownMenuTrigger aria-label="More chart views" className={chartSectionClass}>More</DropdownMenuTrigger><DropdownMenuContent className="w-48"><DropdownMenuGroup>{([ ["history", "History & coverage"], ["timeline", "Timeline"], ["body", "Anatomy"], ["queue", "Approvals"] ] as const).map(([kind, label]) => <DropdownMenuItem key={kind} closeOnClick onClick={() => openTab(kind, patient.id)}>{label}</DropdownMenuItem>)}</DropdownMenuGroup></DropdownMenuContent></DropdownMenu>
        {patient.pendingCount > 0 && <button type="button" onClick={() => openTab("queue", patient.id)} className="rounded bg-watch/10 px-2 py-1 font-semibold text-watch">{patient.pendingCount} pending approvals</button>}
      </nav>}
    </div>
  );
}
