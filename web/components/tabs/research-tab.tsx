"use client";

import { useStore } from "@/lib/store";
import { Page, PageHeader, Section } from "@/components/system/primitives";

export function ResearchTab({ researchId }: { researchId: string }) {
  const result = useStore((s) => s.research[researchId]);
  const patient = useStore((s) => (result ? s.patients[result.patientId] : undefined));
  if (!result || !patient) return null;

  return (
    <Page>
      <PageHeader eyebrow={`Research · ${patient.name}`} title={result.question}>
        {result.basis}
      </PageHeader>
      <p className="mt-10 max-w-3xl font-serif text-[21px] leading-relaxed text-jade-900">{result.answer}</p>
      <Section title="Sources">
        {result.citations.length ? (
          <ol className="space-y-6">
            {result.citations.map((citation, index) => (
              <li key={citation.source} className="grid grid-cols-[1.5rem_1fr] gap-2">
                <span className="numeric text-[13px] text-jade-700">{index + 1}</span>
                <div>
                  <p className="text-[13px] font-semibold text-ink">{citation.source}</p>
                  <blockquote className="mt-2 border-l-2 border-jade-600/40 pl-4 font-serif text-[16px] leading-relaxed text-ink-soft">
                    {citation.passage}
                  </blockquote>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[14px] text-ink-faint">No cited passage was found.</p>
        )}
      </Section>
      <p className="mt-12 text-[12px] text-ink-faint">Cached passages for the demo. A live search goes through Cortex Search.</p>
    </Page>
  );
}
