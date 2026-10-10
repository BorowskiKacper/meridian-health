"use client";

import { useEffect } from "react";
import { ChevronDown, PanelsTopLeft } from "lucide-react";
import { useStore } from "@/lib/store";
import type { Layout } from "@/lib/types";
import { DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AgentWindow } from "@/components/agent/agent-window";
import { Workspace } from "./workspace";

export function Shell() {
  const layout = useStore((s) => s.layout);
  const setLayout = useStore((s) => s.setLayout);
  const status = useStore((s) => s.status);
  const statusMessage = useStore((s) => s.statusMessage);
  const notice = useStore((s) => s.notice);
  const load = useStore((s) => s.load);

  useEffect(() => {
    void load();
  }, [load]);

  if (status !== "ready") {
    return (
      <div className="grid h-full place-items-center bg-jade-50 px-6 text-ink">
        <div className="max-w-md text-center">
          <h1 className="font-serif text-3xl text-jade-900">
            Round<span className="text-jade-600">.</span>
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">{statusMessage}</p>
          {status === "error" && (
            <button
              type="button"
              onClick={() => void load()}
              className="mt-6 h-9 rounded-full bg-jade-600 px-4 text-[13px] text-white hover:bg-jade-700"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-jade-50 text-ink">
      <header className="flex h-14 shrink-0 items-center gap-5 px-5">
        <span className="font-serif text-[25px] tracking-tight text-jade-900">Round<span className="text-jade-600">.</span></span>
        <span className="hidden border-l border-hairline-strong pl-5 text-[12px] text-ink-soft sm:block">Clinical workspace</span>
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="Workspace view"
            className="ml-auto flex h-9 shrink-0 items-center gap-2 rounded-md border border-hairline-strong bg-white px-3 text-[13px] font-semibold text-jade-900 hover:bg-jade-100"
          >
            <PanelsTopLeft className="size-4" />
            View: {layout === "split" ? "Split" : layout === "workspace" ? "Chart" : "Assistant"}
            <ChevronDown className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuRadioGroup value={layout} onValueChange={(value) => setLayout(value as Layout)}>
              <DropdownMenuRadioItem value="split" closeOnClick>Split view</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="workspace" closeOnClick>Chart full screen</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="agent" closeOnClick>Assistant full screen</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      {notice && <p className="shrink-0 border-b border-jade-100 bg-jade-100 px-6 py-2 text-[13px] text-jade-900">{notice}</p>}
      <div className="flex min-h-0 flex-1 gap-3 px-3 pb-3">
        <Workspace hidden={layout === "agent"} />
        <AgentWindow open={layout !== "workspace"} full={layout === "agent"} />
      </div>
    </div>
  );
}
