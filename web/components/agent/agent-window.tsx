"use client";

import { Maximize2, Minimize2, PanelRightClose, Plus, SquareArrowOutUpRight, X } from "lucide-react";
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
import { IconButton } from "@/components/system/icon-button";
import { ConversationView } from "./conversation";

export function AgentWindow({ full }: { full: boolean }) {
  const conversations = useStore((s) => s.conversations);
  const activeId = useStore((s) => s.activeConversationId);
  const activate = useStore((s) => s.activateConversation);
  const close = useStore((s) => s.closeConversation);
  const setLayout = useStore((s) => s.setLayout);
  const setAgentOpen = useStore((s) => s.setAgentOpen);
  const openTab = useStore((s) => s.openTab);
  const active = conversations.find((c) => c.id === activeId);

  return (
    <aside
      className={cn(
        "flex min-h-0 flex-col",
        full ? "flex-1" : "w-[440px] shrink-0 border-l border-hairline",
      )}
      aria-label="Assistant"
    >
      <header className="flex h-12 shrink-0 items-end gap-1 px-4">
        {full && (
          <span className="mr-5 mb-3.5 shrink-0 font-serif text-[17px] text-jade-900">
            Round<span className="text-jade-600">.</span>
          </span>
        )}
        <nav className="flex min-w-0 items-end gap-1 overflow-x-auto" aria-label="Conversations">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={cn(
                "group flex h-9 shrink-0 items-center gap-1 border-b-2 pr-1 pl-2.5 text-[13px]",
                conversation.id === activeId ? "border-jade-600 text-ink" : "border-transparent text-ink-faint hover:text-ink-soft",
              )}
            >
              <button type="button" className="whitespace-nowrap outline-none" onClick={() => activate(conversation.id)}>
                {conversation.title}
              </button>
              <button
                type="button"
                aria-label="Close conversation"
                onClick={() => close(conversation.id)}
                className="grid size-5 place-items-center rounded text-ink-faint opacity-0 group-hover:opacity-100 hover:bg-ivory-deep hover:text-ink focus-visible:opacity-100"
              >
                <X className="size-3" />
              </button>
            </div>
          ))}
          <NewConversationMenu />
        </nav>
        <div className="mb-2 ml-auto flex shrink-0 items-center">
          {active && (
            <IconButton
              label="Open as a tab"
              onClick={() => {
                openTab("chat", active.patientId, active.id);
                setLayout("split");
                setAgentOpen(false);
              }}
            >
              <SquareArrowOutUpRight />
            </IconButton>
          )}
          <IconButton label={full ? "Exit full screen" : "Full screen"} onClick={() => setLayout(full ? "split" : "agent")}>
            {full ? <Minimize2 /> : <Maximize2 />}
          </IconButton>
          {!full && (
            <IconButton label="Hide assistant" onClick={() => setAgentOpen(false)}>
              <PanelRightClose />
            </IconButton>
          )}
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {active ? (
          <ConversationView conversationId={active.id} wide={full} />
        ) : (
          <div className="grid h-full place-items-center px-8 text-center text-sm text-ink-soft">
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
        className="mb-1.5 grid size-7 shrink-0 place-items-center rounded-md text-ink-faint outline-none hover:bg-ivory-deep hover:text-ink"
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
