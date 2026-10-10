"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";
import { AgentWindow } from "@/components/agent/agent-window";
import { Workspace } from "./workspace";

export function Shell() {
  const layout = useStore((s) => s.layout);
  const agentOpen = useStore((s) => s.agentOpen);
  const status = useStore((s) => s.status);
  const statusMessage = useStore((s) => s.statusMessage);
  const notice = useStore((s) => s.notice);
  const load = useStore((s) => s.load);
  const showAgent = layout === "agent" || (layout === "split" && agentOpen);

  useEffect(() => {
    void load();
  }, [load]);

  if (status !== "ready") {
    return (
      <div className="grid h-full place-items-center bg-ivory px-6 text-ink">
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
    <div className="flex h-full flex-col bg-ivory text-ink">
      {notice && <p className="shrink-0 border-b border-hairline bg-white px-6 py-2 text-[13px] text-ink-soft">{notice}</p>}
      <div className="flex min-h-0 flex-1">
        {layout !== "agent" && <Workspace />}
        {showAgent && <AgentWindow full={layout === "agent"} />}
      </div>
    </div>
  );
}
