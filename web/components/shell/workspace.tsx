"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { tabLabel } from "@/lib/data";
import type { WorkTab } from "@/lib/types";
import { PatientSearch } from "./patient-search";
import { TabContent } from "@/components/tabs/tab-content";
import { PatientBanner } from "./patient-banner";
import { initials, patientHue } from "@/lib/data";

export function Workspace({ hidden }: { hidden: boolean }) {
  const tabs = useStore((s) => s.tabs);
  const activeTabId = useStore((s) => s.activeTabId);
  const active = tabs.find((t) => t.id === activeTabId);
  const content = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (content.current) content.current.scrollTop = 0; }, [activeTabId]);

  return (
    <main className={cn("chart-workspace min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-hairline-strong bg-clinical-surface", hidden ? "hidden" : "flex")}>
      <header className="flex h-12 shrink-0 items-end gap-3 border-b border-hairline bg-ivory px-3">
        <TabStrip />
        <PatientSearch />
      </header>
      <section className="min-h-0 flex-1">
        <div className="flex h-full flex-col overflow-hidden">
          {active && <PatientBanner tab={active} />}
          <div ref={content} className="min-h-0 flex-1 overflow-auto">{active ? <TabContent tab={active} /> : <EmptyWorkspace />}</div>
        </div>
      </section>
    </main>
  );
}

function TabStrip() {
  const tabs = useStore((s) => s.tabs);
  const activeTabId = useStore((s) => s.activeTabId);
  const activateTab = useStore((s) => s.activateTab);
  const closeTab = useStore((s) => s.closeTab);
  const moveTab = useStore((s) => s.moveTab);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);

  return (
    <nav className="flex min-w-0 flex-1 items-end gap-1 overflow-x-auto" aria-label="Open tabs">
      {tabs.map((tab, index) => (
        <div
          key={tab.id}
          draggable
          onDragStart={(event) => {
            setDragId(tab.id);
            event.dataTransfer.effectAllowed = "move";
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setOverIndex(index);
          }}
          onDragLeave={() => setOverIndex((i) => (i === index ? null : i))}
          onDrop={(event) => {
            event.preventDefault();
            if (dragId) moveTab(dragId, index);
            setDragId(null);
            setOverIndex(null);
          }}
          onDragEnd={() => {
            setDragId(null);
            setOverIndex(null);
          }}
          onAuxClick={(event) => {
            if (event.button === 1) closeTab(tab.id);
          }}
          className={cn(
            "group relative flex h-9 shrink-0 cursor-default items-center gap-2 border-b-2 pr-1 pl-3 text-[13px] transition-colors",
            tab.id === activeTabId
              ? "border-jade-600 text-ink"
              : "border-transparent text-ink-faint hover:text-ink-soft",
            dragId === tab.id && "opacity-40",
            overIndex === index && dragId !== tab.id && "before:absolute before:top-2 before:bottom-2 before:-left-0.5 before:w-0.5 before:bg-jade-600",
          )}
        >
          <button type="button" aria-current={tab.id === activeTabId ? "page" : undefined} className="flex items-center gap-1.5 outline-none" onClick={() => activateTab(tab.id)}>
            <PatientMark patientId={tab.patientId} />
            <TabTitle tab={tab} />
          </button>
          <button
            type="button"
            aria-label="Close tab"
            onClick={() => closeTab(tab.id)}
            className="grid size-5 place-items-center rounded text-ink-faint opacity-0 transition-opacity group-hover:opacity-100 hover:bg-ivory-deep hover:text-ink focus-visible:opacity-100"
          >
            <X className="size-3" />
          </button>
        </div>
      ))}
    </nav>
  );
}

function TabTitle({ tab }: { tab: WorkTab }) {
  const patient = useStore((s) => s.patients[tab.patientId]);
  const finding = patient?.findings.find((f) => f.id === tab.refId);
  const title =
    tab.kind === "region" && finding ? finding.title : tab.kind === "timeline" && tab.refId === "notes" ? "Notes" : tabLabel[tab.kind];
  const surname = patient?.name.split(" ").at(-1);
  return (
    <>
      <span className="whitespace-nowrap">{title}</span>
      <span className="text-[11px] whitespace-nowrap text-ink-faint">{surname}</span>
    </>
  );
}

function PatientMark({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  if (!patient) return null;
  return (
    <span
      aria-hidden
      title={patient.name}
      className="grid size-4 place-items-center rounded-full text-[8px] font-semibold text-jade-900"
      style={{ background: patientHue(patient.id) }}
    >
      {initials(patient.name)}
    </span>
  );
}

function EmptyWorkspace() {
  return (
    <div className="grid h-full place-items-center">
      <div className="max-w-sm text-center">
        <h2 className="text-2xl">No tabs open</h2>
        <p className="mt-2 text-sm text-ink-soft">Open a patient view with the plus button, or ask the assistant to open one.</p>
      </div>
    </div>
  );
}
