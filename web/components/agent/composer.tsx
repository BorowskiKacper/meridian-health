"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import type { Mode } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const modes: { id: Mode; label: string; hint: string }[] = [
  { id: "auto", label: "Auto", hint: "Routes each request to the right agent" },
  { id: "chart", label: "Chart", hint: "Dictation becomes chart changes to approve" },
  { id: "research", label: "Ask", hint: "Clinical questions, answered with citations" },
  { id: "screening", label: "Screening", hint: "Reviews screenings and reminders" },
];

/** Stand-in for speech-to-text until Scribe is connected. */
const transcripts: Record<string, Record<Mode, string>> = {
  nora: {
    auto: "The left fibula is tender after the kerb strike. Watch it.",
    chart: "LDL is 190. Her father had an MI at 55. Start lisinopril 10 mg.",
    research: "Should she start a statin given her history?",
    screening: "Are her screenings up to date?",
  },
  marcus: {
    auto: "A1c is 8.4 today. Continue metformin and recheck in three months.",
    chart: "A1c is 8.4 today. Continue metformin and recheck in three months.",
    research: "Should we add an SGLT2 inhibitor given his kidneys?",
    screening: "Is he due for any screenings?",
  },
};

const LISTEN_MS = 1600;

export function Composer({ conversationId }: { conversationId: string }) {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const send = useStore((s) => s.send);
  const activate = useStore((s) => s.activateConversation);
  const patient = useStore((s) => {
    const conversation = s.conversations.find((c) => c.id === conversationId);
    return conversation ? s.patients[conversation.patientId] : undefined;
  });
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!listening || !patient) return;
    const timer = setTimeout(() => {
      setText(transcripts[patient.id]?.[mode] ?? "");
      setListening(false);
      field.current?.focus();
    }, LISTEN_MS);
    return () => clearTimeout(timer);
  }, [listening, mode, patient]);

  const submit = () => {
    const value = text.trim();
    if (!value) return;
    activate(conversationId);
    send(value);
    setText("");
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="rounded-2xl border border-hairline-strong bg-white shadow-[0_1px_2px_rgb(0_54_45/0.04),0_8px_24px_-12px_rgb(0_54_45/0.12)] focus-within:border-jade-600/50"
    >
      <textarea
        ref={field}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder={listening ? "Listening…" : `Message about ${patient?.name ?? "this patient"}`}
        className="field-sizing-content block max-h-48 min-h-12 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[14px] leading-relaxed text-ink outline-none placeholder:text-ink-faint"
      />
      <div className="flex items-center gap-2 px-2 pb-2">
        <div role="radiogroup" aria-label="Mode" className="flex items-center gap-0.5">
          {modes.map((item) => (
            <Tooltip key={item.id}>
              <TooltipTrigger
                type="button"
                role="radio"
                aria-checked={mode === item.id}
                onClick={() => setMode(item.id)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[12px] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  mode === item.id ? "bg-jade-50 font-semibold text-jade-900" : "text-ink-faint hover:text-ink",
                )}
              >
                {item.label}
              </TooltipTrigger>
              <TooltipContent>{item.hint}</TooltipContent>
            </Tooltip>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger
              type="button"
              aria-label={listening ? "Stop dictation" : "Dictate"}
              aria-pressed={listening}
              onClick={() => setListening((value) => !value)}
              className={cn(
                "relative grid size-8 place-items-center rounded-full outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                listening ? "bg-jade-50 text-jade-700" : "text-ink-faint hover:bg-ivory-deep hover:text-ink",
              )}
            >
              {listening && <span className="listening-ring absolute inset-0 rounded-full bg-jade-300/50" />}
              <Mic className="relative size-4" />
            </TooltipTrigger>
            <TooltipContent>Dictate. The transcript fills in for you to review.</TooltipContent>
          </Tooltip>
          <button
            type="submit"
            aria-label="Send"
            disabled={!text.trim()}
            className="grid size-8 place-items-center rounded-full bg-jade-600 text-white transition-colors hover:bg-jade-700 disabled:bg-ivory-deep disabled:text-ink-faint"
          >
            <ArrowUp className="size-4" />
          </button>
        </div>
      </div>
    </form>
  );
}
