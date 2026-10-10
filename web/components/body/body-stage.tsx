"use client";

import { useEffect, useState, type ReactNode, type RefObject } from "react";
import { Crosshair, Layers, LocateFixed, Rotate3d, Ruler, Search, StickyNote, X, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { BodyScene } from "./scene/controller";
import type { CutAxis, LookupHit, SceneSnapshot, Tool } from "./scene/types";

const tools: { id: Tool; label: string; key: string; icon: ReactNode }[] = [
  { id: "orbit", label: "Orbit", key: "O", icon: <Rotate3d /> },
  { id: "probe", label: "Probe", key: "P", icon: <Crosshair /> },
  { id: "measure", label: "Measure", key: "M", icon: <Ruler /> },
  { id: "mark", label: "Note", key: "N", icon: <StickyNote /> },
];

const axes: { id: CutAxis; label: string }[] = [
  { id: "y", label: "Height" },
  { id: "x", label: "Side" },
  { id: "z", label: "Depth" },
];

export function BodyStage({
  viewRef,
  labelsRef,
  scene,
  snapshot,
  retry,
  className,
}: {
  viewRef: RefObject<HTMLDivElement | null>;
  labelsRef: RefObject<HTMLDivElement | null>;
  scene: BodyScene | null;
  snapshot: SceneSnapshot;
  retry: () => void;
  className?: string;
}) {
  const ready = snapshot.status === "ready";

  return (
    <div
      data-tool={snapshot.tool}
      className={cn("body-stage relative isolate overflow-hidden rounded-xl bg-[#101a17]", className)}
    >
      <div ref={viewRef} className="absolute inset-0 [&_canvas]:block [&_canvas]:size-full" />
      <div ref={labelsRef} className="body-labels pointer-events-none absolute inset-0" />

      {ready && (
        <>
          <div className="pointer-events-none absolute top-4 left-4 flex max-w-[min(26rem,calc(100%-20rem))] flex-col gap-2">
            {snapshot.hud && (
              <p className="w-fit rounded-md bg-black/35 px-3 py-1.5 text-[12px] leading-snug text-ivory/85 backdrop-blur-sm">
                {snapshot.hud}
              </p>
            )}
          </div>
          <Lookup scene={scene} />
          <Toolbar scene={scene} snapshot={snapshot} />
        </>
      )}

      {snapshot.status === "loading" && (
        <div className="absolute inset-0 grid place-items-center">
          <div className="w-56 text-center">
            <p className="font-serif text-[17px] text-ivory/90">{snapshot.loadingText}</p>
            <div className="mt-4 h-px w-full overflow-hidden bg-white/10">
              <div className="h-full bg-jade-300 transition-[width] duration-300" style={{ width: `${Math.round(snapshot.progress * 100)}%` }} />
            </div>
          </div>
        </div>
      )}

      {snapshot.status === "error" && (
        <div className="absolute inset-0 grid place-items-center p-8">
          <div className="max-w-sm text-center">
            <p className="font-serif text-[19px] text-ivory">The anatomy did not load</p>
            <p className="mt-2 text-[13px] leading-relaxed text-ivory/60">{snapshot.error}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-5 rounded-md border border-white/15 px-3.5 py-1.5 text-[13px] text-ivory hover:bg-white/10"
            >
              Try again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Toolbar({ scene, snapshot }: { scene: BodyScene | null; snapshot: SceneSnapshot }) {
  return (
    <div className="absolute inset-x-0 bottom-4 flex flex-col items-center gap-2 px-4">
      {snapshot.cutaway && (
        <div className="flex w-full max-w-xl items-center gap-4 rounded-lg bg-[#0b1311]/85 px-4 py-2.5 text-ivory backdrop-blur-md">
          <div role="radiogroup" aria-label="Cut direction" className="flex shrink-0 gap-1">
            {axes.map((axis) => (
              <button
                key={axis.id}
                type="button"
                role="radio"
                aria-checked={snapshot.cutAxis === axis.id}
                onClick={() => scene?.setCutAxis(axis.id)}
                className={cn(
                  "rounded px-2 py-1 text-[11px] font-semibold tracking-[0.12em] uppercase",
                  snapshot.cutAxis === axis.id ? "bg-white/12 text-ivory" : "text-ivory/50 hover:text-ivory/80",
                )}
              >
                {axis.label}
              </button>
            ))}
          </div>
          <input
            type="range"
            min={0}
            max={1000}
            value={Math.round(snapshot.cutT * 1000)}
            onChange={(event) => scene?.setCutT(Number(event.target.value) / 1000)}
            aria-label="Cut depth"
            className="min-w-0 flex-1 accent-jade-300"
          />
          <span className="numeric w-44 shrink-0 text-right text-[12px] text-ivory/65">{snapshot.cutCaption}</span>
        </div>
      )}

      <div className="flex items-center gap-1 rounded-lg bg-[#0b1311]/85 p-1 text-ivory backdrop-blur-md">
        <div role="radiogroup" aria-label="Tool" className="flex gap-0.5">
          {tools.map((tool) => (
            <StageButton
              key={tool.id}
              role="radio"
              pressed={snapshot.tool === tool.id}
              hint={`${tool.label} · ${tool.key}`}
              onClick={() => scene?.setTool(tool.id)}
            >
              {tool.icon}
              {tool.label}
            </StageButton>
          ))}
        </div>
        <span aria-hidden className="mx-1 h-5 w-px bg-white/12" />
        <StageButton pressed={snapshot.impacts} hint="Impact arrows · I" onClick={() => scene?.toggleImpacts()}>
          <Zap />
          Impacts
        </StageButton>
        <StageButton pressed={snapshot.cutaway} hint="Cut away tissue · C" onClick={() => scene?.toggleCutaway()}>
          <Layers />
          Cutaway
        </StageButton>
        <span aria-hidden className="mx-1 h-5 w-px bg-white/12" />
        <StageButton hint="Front view" onClick={() => scene?.resetView()}>
          <LocateFixed />
        </StageButton>
        {(snapshot.measures > 0 || snapshot.notes > 0) && (
          <StageButton
            hint="Clear measurements and notes"
            onClick={() => {
              scene?.clearMeasures();
              scene?.clearNotes();
            }}
          >
            <X />
            Clear
          </StageButton>
        )}
      </div>
    </div>
  );
}

function StageButton({
  pressed,
  hint,
  role,
  onClick,
  children,
}: {
  pressed?: boolean;
  hint: string;
  role?: "radio";
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        type="button"
        role={role}
        aria-checked={role === "radio" ? pressed : undefined}
        aria-pressed={role ? undefined : pressed}
        aria-label={hint}
        onClick={onClick}
        className={cn(
          "flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12.5px] transition-colors [&_svg]:size-3.5",
          pressed ? "bg-white/12 text-ivory" : "text-ivory/60 hover:bg-white/6 hover:text-ivory",
        )}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent side="top">{hint}</TooltipContent>
    </Tooltip>
  );
}

function Lookup({ scene }: { scene: BodyScene | null }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState<string[]>([]);
  const hits: LookupHit[] = scene && open ? scene.search(query) : [];

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!(event.target as HTMLElement).closest(".body-lookup")) setOpen(false);
    };
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [open]);

  const reveal = (hit: LookupHit) => {
    setQuery("");
    setOpen(false);
    setShown((list) => (list.includes(hit.label) ? list : [...list, hit.label]));
    void scene?.reveal(hit);
  };

  return (
    <div className="body-lookup absolute top-4 right-4 w-72">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (hits[0]) reveal(hits[0]);
        }}
        className="flex h-9 items-center gap-2 rounded-lg bg-[#0b1311]/85 px-3 text-ivory backdrop-blur-md focus-within:ring-1 focus-within:ring-jade-300/60"
      >
        <Search className="size-3.5 shrink-0 text-ivory/50" />
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
          placeholder="Look up a structure"
          aria-label="Look up a structure"
          className="min-w-0 flex-1 bg-transparent text-[13px] text-ivory outline-none placeholder:text-ivory/40"
        />
        {shown.length > 0 && (
          <button
            type="button"
            onClick={() => {
              scene?.clearLookups();
              setShown([]);
            }}
            className="shrink-0 text-[11px] text-ivory/50 hover:text-ivory"
          >
            Clear {shown.length}
          </button>
        )}
      </form>
      {open && hits.length > 0 && (
        <ul className="mt-1.5 overflow-hidden rounded-lg bg-[#0b1311]/92 py-1 backdrop-blur-md">
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                onClick={() => reveal(hit)}
                className="block w-full px-3 py-2 text-left hover:bg-white/8"
              >
                <span className="block text-[13px] text-ivory">{hit.label}</span>
                {hit.latin && <span className="block font-serif text-[12px] text-ivory/45 italic">{hit.latin}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
