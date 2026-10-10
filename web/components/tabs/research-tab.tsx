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
      <p className="mt-8 max-w-3xl whitespace-pre-wrap break-words text-[16px] leading-relaxed text-ink">{result.answer}</p>
      <Section title="Sources">
        {result.citations.length ? (
          <ol className="space-y-6">
            {result.citations.map((citation, index) => (
              <li key={citation.source} className="grid grid-cols-[1.5rem_1fr] gap-2">
                <span className="numeric text-[13px] text-jade-700">{index + 1}</span>
                <div>
                  <p className="break-words text-[13px] font-semibold text-ink">{citation.source}</p>
                  <blockquote className="mt-3 border-l-2 border-hairline-strong pl-4 text-[14px] leading-relaxed text-ink-soft">
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
      <p className="mt-12 text-[12px] text-ink-faint">Citations returned by the clinic API.</p>
    </Page>
  );
}
