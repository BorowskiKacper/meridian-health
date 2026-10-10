"use client";

import { kindLabel, whenLabel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Page, PageHeader, SeverityDot } from "@/components/system/primitives";
import type { Severity } from "@/lib/types";

interface Entry {
  id: string;
  minute: number;
  title: string;
  detail: string;
  kind: string;
  severity?: Severity;
  findingId?: string;
}

export function TimelineTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;

  const entries: Entry[] = [
    ...patient.findings.map((f) => ({
      id: f.id,
      minute: f.minute,
      title: f.title,
      detail: f.condition,
      kind: kindLabel[f.kind],
      severity: f.severity,
      findingId: f.id,
    })),
    ...patient.notes.map((n) => ({ id: n.id, minute: n.minute, title: "Note", detail: n.text, kind: "Note" })),
  ].sort((a, b) => b.minute - a.minute);

  const groups = entries.reduce<Record<string, Entry[]>>((acc, entry) => {
    (acc[whenLabel(entry.minute)] ??= []).push(entry);
    return acc;
  }, {});

  return (
    <Page>
      <PageHeader eyebrow={patient.name} title="Timeline">
        Approved chart entries, newest first. Pending suggestions do not appear here until you approve them.
      </PageHeader>
      <div className="mt-12 space-y-12">
        {Object.entries(groups).map(([when, items]) => (
          <section key={when} className="grid gap-6 md:grid-cols-[10rem_1fr]">
            <h2 className="eyebrow font-sans pt-1">{when}</h2>
            <ol className="divide-y divide-hairline border-t border-hairline">
              {items.map((entry) => (
                <li key={entry.id}>
                  <button
                    type="button"
                    disabled={!entry.findingId}
                    onClick={() => entry.findingId && openTab("region", patientId, entry.findingId)}
                    className="group flex w-full items-baseline gap-3 py-3.5 text-left disabled:cursor-default"
                  >
                    {entry.severity ? <SeverityDot severity={entry.severity} /> : <span className="size-2 shrink-0" />}
                    <span className="min-w-0 flex-1">
                      <span className="font-serif text-[17px] text-jade-900 group-enabled:group-hover:text-jade-600">{entry.title}</span>
                      <span className="mt-0.5 block text-[13px] text-ink-soft">{entry.detail}</span>
                    </span>
                    <span className="text-[11px] tracking-[0.1em] text-ink-faint uppercase">{entry.kind}</span>
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
