"use client";

import { kindLabel, severityLabel, whenLabel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Page, PageHeader, Section, SeverityDot } from "@/components/system/primitives";

export function RegionTab({ patientId, findingId }: { patientId: string; findingId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const finding = patient?.findings.find((f) => f.id === findingId);
  if (!patient || !finding) return null;
  const notes = patient.notes.filter((n) => n.findingId === finding.id);

  return (
    <Page>
      <PageHeader eyebrow={`${patient.name} · ${kindLabel[finding.kind]}`} title={finding.title}>
        <span className="flex items-center gap-2">
          <SeverityDot severity={finding.severity} />
          {finding.condition}
        </span>
      </PageHeader>

      <p className="mt-8 max-w-2xl font-serif text-[19px] leading-relaxed text-jade-900">{finding.note}</p>
      <p className="mt-3 text-[13px] text-ink-faint">
        {severityLabel[finding.severity]} · {whenLabel(finding.minute)} · {finding.structureId}
      </p>

      <div className="grid gap-x-16 md:grid-cols-2">
        <Section title="Observations">
          <dl className="divide-y divide-hairline">
            {finding.observations.map((o) => (
              <div key={o.label} className="flex justify-between gap-6 py-2.5 text-[14px]">
                <dt className="text-ink-soft">{o.label}</dt>
                <dd className="numeric text-ink">{o.value}</dd>
              </div>
            ))}
          </dl>
        </Section>
        <Section title="Medications">
          {finding.meds.length ? (
            <ul className="divide-y divide-hairline">
              {finding.meds.map((m) => (
                <li key={m} className="py-2.5 text-[14px] text-ink">
                  {m}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[14px] text-ink-faint">None charted</p>
          )}
        </Section>
      </div>

      <Section title="Family history">
        <ul className="space-y-1.5 text-[14px] text-ink">
          {patient.family.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </Section>

      {notes.length > 0 && (
        <Section title="Notes">
          <ul className="space-y-3 text-[14px] leading-relaxed text-ink">
            {notes.map((n) => (
              <li key={n.id}>{n.text}</li>
            ))}
          </ul>
        </Section>
      )}
    </Page>
  );
}
