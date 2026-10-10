"use client";

import { useStore } from "@/lib/store";
import { AgentWindow } from "@/components/agent/agent-window";
import { Workspace } from "./workspace";

export function Shell() {
  const layout = useStore((s) => s.layout);
  const agentOpen = useStore((s) => s.agentOpen);
  const showAgent = layout === "agent" || (layout === "split" && agentOpen);

  return (
    <div className="flex h-full bg-ivory text-ink">
      {layout !== "agent" && <Workspace />}
      {showAgent && <AgentWindow full={layout === "agent"} />}
    </div>
  );
}
