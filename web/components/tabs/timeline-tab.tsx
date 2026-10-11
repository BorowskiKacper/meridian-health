"use client";

import { formatDate, kindLabel, firstName } from "@/lib/data";
import { useStore } from "@/lib/store";
import type { ChartNote } from "@/lib/types";
import { Page, PageHeader, SeverityDot } from "@/components/system/primitives";

const kindText: Record<ChartNote["kind"], string> = {
  visit: "Visit",
  procedure: "Procedure",
  note: "Note",
  medication: "Medication",
};

export function TimelineTab({ patientId, notesOnly = false }: { patientId: string; notesOnly?: boolean }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;

  const findings = [...patient.findings]
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
    .map((f) => ({
      id: f.id,
      at: f.at,
      title: f.title,
      detail: f.condition,
      kind: kindLabel[f.kind],
      severity: f.severity,
      findingId: f.id,
    }));

  const entries = patient.notes.filter((n) => !notesOnly || n.kind === "note").sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  const years = entries.reduce<Record<string, ChartNote[]>>((acc, entry) => {
    const year = new Date(entry.at).getUTCFullYear().toString();
    (acc[year] ??= []).push(entry);
    return acc;
  }, {});

  return (
    <Page>
      <PageHeader eyebrow={patient.name} title={`${firstName(patient.name)}’s ${notesOnly ? "Notes" : "Timeline"}`}>
        {notesOnly ? "Clinical notes, newest first." : "Encounters, medication starts and notes, newest first."}
      </PageHeader>

      {!notesOnly && findings.length > 0 && (
        <details className="mt-8 border-t border-hairline pt-4">
          <summary className="w-fit cursor-pointer text-[13px] font-medium text-jade-700">Related chart regions · {findings.length}</summary>
          <ol className="mt-4 divide-y divide-hairline border-t border-hairline">
            {findings.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => openTab("region", patientId, entry.findingId)}
                  className="group flex w-full flex-wrap items-baseline gap-3 py-5 text-left"
                >
                  <SeverityDot severity={entry.severity} />
                  <span className="min-w-0 flex-1 basis-40">
                    <span className="font-serif text-[17px] text-jade-900 group-hover:text-jade-600">{entry.title}</span>
                    <span className="mt-0.5 block text-[13px] text-ink-soft">{entry.detail}</span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block text-[12px] text-ink-faint">{formatDate(entry.at)}</span>
                    <span className="text-[11px] tracking-[0.1em] text-ink-faint uppercase">{entry.kind}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </details>
      )}

      <div className="mt-12 space-y-12">
        {Object.entries(years).sort(([a], [b]) => Number(b) - Number(a)).map(([year, items]) => (
          <section key={year} className="grid gap-4 @min-[800px]:grid-cols-[5rem_1fr]">
            <h2 className="eyebrow font-sans pt-1">{year}</h2>
            <ol className="divide-y divide-hairline border-t border-hairline">
              {items.map((entry) => (
                <li key={entry.id}>
                  <button
                    type="button"
                    disabled={!entry.findingId}
                    onClick={() => entry.findingId && openTab("region", patientId, entry.findingId)}
                    className="group grid w-full min-w-0 gap-y-3 py-5 text-left disabled:cursor-default"
                  >
                    <span className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-faint"><span className="numeric">{formatDate(entry.at)}</span><span>{kindText[entry.kind]}</span></span>
                    <span className="min-w-0 text-[14px] leading-relaxed text-ink group-enabled:group-hover:text-jade-600">{entry.text}</span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </Page>
  );
}
