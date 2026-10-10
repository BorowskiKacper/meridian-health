"use client";

import { useState } from "react";
import { Maximize2, Minimize2, MessageSquare, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { openableTabs, tabLabel } from "@/lib/data";
import type { WorkTab } from "@/lib/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { IconButton } from "@/components/system/icon-button";
import { TabContent } from "@/components/tabs/tab-content";

export function Workspace() {
  const tabs = useStore((s) => s.tabs);
  const activeTabId = useStore((s) => s.activeTabId);
  const layout = useStore((s) => s.layout);
  const agentOpen = useStore((s) => s.agentOpen);
  const setLayout = useStore((s) => s.setLayout);
  const setAgentOpen = useStore((s) => s.setAgentOpen);
  const active = tabs.find((t) => t.id === activeTabId);
  const assistantHidden = layout === "workspace" || !agentOpen;

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-12 shrink-0 items-end gap-6 px-6">
        <span className="mb-3.5 shrink-0 font-serif text-[17px] text-jade-900">
          Round<span className="text-jade-600">.</span>
        </span>
        <TabStrip />
        <div className="mb-2 ml-auto flex shrink-0 items-center gap-1">
          <IconButton
            label={layout === "workspace" ? "Exit full screen" : "Full screen"}
            onClick={() => setLayout(layout === "workspace" ? "split" : "workspace")}
          >
            {layout === "workspace" ? <Minimize2 /> : <Maximize2 />}
          </IconButton>
          {assistantHidden && (
            <IconButton
              label="Show assistant"
              onClick={() => {
                setLayout("split");
                setAgentOpen(true);
              }}
            >
              <MessageSquare />
            </IconButton>
          )}
        </div>
      </header>
      <section className="min-h-0 flex-1 px-3 pb-3">
        <div className="h-full overflow-auto rounded-xl border border-hairline bg-white">
          {active ? <TabContent tab={active} /> : <EmptyWorkspace />}
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
    <nav className="flex min-w-0 items-end gap-1 overflow-x-auto" aria-label="Open tabs">
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
          <button type="button" className="flex items-baseline gap-1.5 outline-none" onClick={() => activateTab(tab.id)}>
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
      <NewTabMenu />
    </nav>
  );
}

function TabTitle({ tab }: { tab: WorkTab }) {
  const patient = useStore((s) => s.patients[tab.patientId]);
  const finding = patient?.findings.find((f) => f.id === tab.refId);
  const conversation = useStore((s) => s.conversations.find((c) => c.id === tab.refId));
  const title =
    tab.kind === "region" && finding ? finding.title : tab.kind === "chat" && conversation ? "Conversation" : tabLabel[tab.kind];
  const surname = patient?.name.split(" ").at(-1);
  return (
    <>
      <span className="whitespace-nowrap">{title}</span>
      <span className="text-[11px] whitespace-nowrap text-ink-faint">{surname}</span>
    </>
  );
}

function NewTabMenu() {
  const patients = useStore((s) => s.patients);
  const openTab = useStore((s) => s.openTab);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Open a tab"
        className="mb-1.5 grid size-7 shrink-0 place-items-center rounded-md text-ink-faint outline-none hover:bg-ivory-deep hover:text-ink"
      >
        <Plus className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        {Object.values(patients).map((patient, index) => (
          <DropdownMenuGroup key={patient.id}>
            {index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel>{patient.name}</DropdownMenuLabel>
            {openableTabs.map((kind) => (
              <DropdownMenuItem key={kind} onClick={() => openTab(kind, patient.id)}>
                {tabLabel[kind]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
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
