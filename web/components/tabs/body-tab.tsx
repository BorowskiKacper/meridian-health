"use client";

import { useEffect, useMemo } from "react";
import { ArrowUpRight, Footprints, Square } from "lucide-react";
import { findingVisible, kindLabel, severityLabel, specialtyLabel, whenLabel, NOW_MINUTE } from "@/lib/data";
import { useStore } from "@/lib/store";
import type { Finding, Specialty } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Page, PageHeader, SeverityDot } from "@/components/system/primitives";
import { BodyStage } from "@/components/body/body-stage";
import { useBodyScene } from "@/components/body/use-body-scene";
import type { BodyScene } from "@/components/body/scene/controller";

export function BodyTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const view = useStore((s) => s.views[patientId]);
  const setView = useStore((s) => s.setView);
  const openTab = useStore((s) => s.openTab);

  const visible = useMemo(
    () =>
      patient && view
        ? patient.findings.filter((f) => findingVisible(f, view.minute, view.specialty)).sort((a, b) => b.minute - a.minute)
        : [],
    [patient, view],
  );
  const { scene, snapshot, viewRef, labelsRef, retry } = useBodyScene(visible);
  useShortcuts(scene, visible);

  if (!patient || !view) return null;
  const specialties: Specialty[] = ["all", ...patient.specialties];
  const ready = snapshot.status === "ready";

  return (
    <Page wide>
      <PageHeader
        eyebrow={`${patient.mrn} · ${patient.age} ${patient.sex}`}
        title={patient.name}
        actions={
          <button
            type="button"
            disabled={!ready || visible.length === 0}
            onClick={() => void scene?.walk()}
            className="flex h-9 items-center gap-2 rounded-md border border-hairline-strong bg-white px-3.5 text-[13px] text-jade-900 hover:bg-jade-50 disabled:opacity-40"
          >
            {snapshot.walking ? <Square className="size-3.5" /> : <Footprints className="size-3.5" />}
            {snapshot.walking ? "Stop the walk" : "Walk the marks"}
          </button>
        }
      >
        {patient.summary}
      </PageHeader>

      <div className="mt-10 flex flex-wrap items-end gap-10 border-b border-hairline pb-6">
        <label className="grid gap-2">
          <span className="eyebrow">Specialty</span>
          <Select
            value={view.specialty}
            items={specialties.map((s) => ({ value: s, label: specialtyLabel[s] }))}
            onValueChange={(value) => value && setView(patientId, { specialty: value as Specialty })}
          >
            <SelectTrigger className="h-9 min-w-44 bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {specialties.map((s) => (
                <SelectItem key={s} value={s}>
                  {specialtyLabel[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <div className="grid min-w-64 flex-1 gap-3">
          <span className="eyebrow flex justify-between">
            <span>Timeline</span>
            <span className="font-normal tracking-normal normal-case text-ink-soft">{whenLabel(view.minute)}</span>
          </span>
          <Slider
            value={[view.minute]}
            max={NOW_MINUTE}
            onValueChange={(value) => setView(patientId, { minute: Array.isArray(value) ? value[0]! : value })}
            aria-label="Timeline"
          />
        </div>
      </div>

      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <BodyStage
          viewRef={viewRef}
          labelsRef={labelsRef}
          scene={scene}
          snapshot={snapshot}
          retry={retry}
          className="h-[min(72vh,720px)] min-h-[460px]"
        />

        <div>
          <p className="eyebrow">
            {visible.length} {visible.length === 1 ? "finding" : "findings"} · {specialtyLabel[view.specialty]}
          </p>
          {visible.length === 0 ? (
            <p className="mt-4 text-sm text-ink-soft">Nothing for this time and specialty. Move the timeline forward or choose All findings.</p>
          ) : (
            <ol className="mt-3 divide-y divide-hairline">
              {visible.map((finding, index) => {
                const active = ready && finding.id === snapshot.activeId;
                const latin = active ? scene?.latin(finding.structureId) : undefined;
                return (
                  <li key={finding.id}>
                    <button
                      type="button"
                      onClick={() => (ready ? scene?.choose(finding.id) : openTab("region", patientId, finding.id))}
                      aria-current={active || undefined}
                      className="group grid w-full grid-cols-[auto_1fr_auto] items-baseline gap-x-3 pt-4 pb-3 text-left"
                    >
                      <SeverityDot severity={finding.severity} className="translate-y-[-1px]" />
                      <span
                        className={cn(
                          "font-serif text-[18px] group-hover:text-jade-600",
                          active ? "text-jade-600" : "text-jade-900",
                        )}
                      >
                        {finding.title}
                      </span>
                      {index < 9 && <kbd className="numeric font-sans text-[11px] text-ink-faint">{index + 1}</kbd>}
                      <span />
                      <span className="col-span-2 mt-0.5 text-[13px] text-ink-soft">{finding.condition}</span>
                      <span />
                      <span className="col-span-2 mt-1 text-[11px] tracking-[0.1em] text-ink-faint uppercase">
                        {kindLabel[finding.kind]} · {severityLabel[finding.severity]} · {whenLabel(finding.minute)}
                      </span>
                    </button>
                    {active && (
                      <div className="ml-5 pb-4">
                        <p className="text-[13px] leading-relaxed text-ink-soft">{finding.note}</p>
                        {latin && <p className="mt-1.5 font-serif text-[13px] text-ink-faint italic">{latin}</p>}
                        <button
                          type="button"
                          onClick={() => openTab("region", patientId, finding.id)}
                          className="mt-2.5 inline-flex items-center gap-1 text-[13px] text-jade-600 hover:text-jade-700"
                        >
                          Open region
                          <ArrowUpRight className="size-3.5" />
                        </button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
          <p className="mt-8 text-[12px] leading-relaxed text-ink-faint">
            Drag to orbit. Numbers jump to a finding; O, P, M and N switch tools; I toggles impacts and C the cutaway.
          </p>
        </div>
      </div>
    </Page>
  );
}

function useShortcuts(scene: BodyScene | null, visible: Finding[]) {
  useEffect(() => {
    if (!scene) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (target?.closest("input, textarea, select, [contenteditable='true'], [role='combobox'], [role='listbox']")) return;
      const digit = Number(event.key);
      if (digit >= 1 && digit <= visible.length) {
        scene.choose(visible[digit - 1]!.id);
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "escape" || key === "o") scene.setTool("orbit");
      else if (key === "p") scene.setTool("probe");
      else if (key === "m") scene.setTool("measure");
      else if (key === "n") scene.setTool("mark");
      else if (key === "i") scene.toggleImpacts();
      else if (key === "c") scene.toggleCutaway();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scene, visible]);
}
