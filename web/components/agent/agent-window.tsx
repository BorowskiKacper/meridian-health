"use client";

import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConversationView } from "./conversation";

export function AgentWindow({ open, full }: { open: boolean; full: boolean }) {
  const conversations = useStore((s) => s.conversations);
  const activeId = useStore((s) => s.activeConversationId);
  const activate = useStore((s) => s.activateConversation);
  const active = conversations.find((c) => c.id === activeId);

  return (
    <aside
      id="assistant-panel"
      className={cn(
        "agent-window min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-hairline-strong bg-assistant-surface text-ivory",
        full ? "flex-1" : "assistant-panel shrink-0",
        open ? "flex" : "hidden",
      )}
      aria-label="Assistant"
    >
      <header className="flex h-12 shrink-0 items-end gap-1 border-b border-white/20 px-3">
        <nav className="flex min-w-0 items-end gap-1 overflow-x-auto" aria-label="Conversations">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={cn(
                "group flex h-9 shrink-0 items-center gap-1 border-b-2 pr-1 pl-2 text-[12px]",
                conversation.id === activeId ? "border-jade-300 text-ivory" : "border-transparent text-ivory/80 hover:text-ivory",
              )}
            >
              <button type="button" aria-pressed={conversation.id === activeId} className="whitespace-nowrap outline-none" onClick={() => activate(conversation.id)}>
                {conversation.title}
              </button>
            </div>
          ))}
        </nav>
        <NewConversationMenu />
      </header>
      <div className="min-h-0 flex-1">
        {active ? (
          <ConversationView conversationId={active.id} wide={full} />
        ) : (
          <div className="agent-dim grid h-full place-items-center px-8 text-center text-sm">
            Start a conversation with the plus button.
          </div>
        )}
      </div>
    </aside>
  );
}

function NewConversationMenu() {
  const patients = useStore((s) => s.patients);
  const newConversation = useStore((s) => s.newConversation);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="New conversation"
        className="mb-1.5 grid size-7 shrink-0 place-items-center rounded-md text-ivory/80 outline-none hover:bg-white/10 hover:text-ivory"
      >
        <Plus className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-52">
        <DropdownMenuGroup>
          <DropdownMenuLabel>New conversation about</DropdownMenuLabel>
          {Object.values(patients).map((patient) => (
            <DropdownMenuItem key={patient.id} onClick={() => newConversation(patient.id)}>
              {patient.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
