"use client";

import { ResearchResult } from "@/components/agent/research-result";
import { useStore } from "@/lib/store";
import { Page, PageHeader } from "@/components/system/primitives";

export function ResearchTab({ researchId }: { researchId: string }) {
  const result = useStore((s) => s.research[researchId]);
  const patient = useStore((s) => (result?.patientId ? s.patients[result.patientId] : undefined));
  if (!result || (result.patientId && !patient)) return null;

  return (
    <Page>
      <PageHeader eyebrow={`Research · ${patient?.name ?? "General"}`} title={result.question}>

      </PageHeader>
      <ResearchResult result={result} />
    </Page>
  );
}
