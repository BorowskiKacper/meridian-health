"use client";

import { labPanel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/system/primitives";

export function LabTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const extracted = useStore((s) => Boolean(s.uploadedLabs[patientId]));
  const extractLab = useStore((s) => s.extractLab);
  if (!patient) return null;

  return (
    <Page>
      <PageHeader
        eyebrow={`${patient.name} · Synthetic sample document`}
        title="Lab report"
        actions={
          <Button className="max-w-full whitespace-normal rounded-md px-4" disabled={extracted} onClick={() => extractLab(patientId)}>
            {extracted ? "Drafts sent to the assistant" : "Extract values"}
          </Button>
        }
      >
        Sample report preview for the extraction workflow.
      </PageHeader>

      <figure className="mt-8 rounded-lg border border-hairline bg-ivory p-3 @min-[700px]:p-6">
        <div className="mx-auto max-w-3xl bg-white px-4 py-6 @min-[700px]:px-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-ink/80 pb-4">
            <p className="font-serif text-[18px] text-ink">{labPanel.lab}</p>
            <p className="text-[12px] text-ink-soft">{labPanel.collected}</p>
          </div>
          <p className="mt-4 text-[13px] text-ink-soft">
            {labPanel.title} · Patient: {patient.name}
          </p>
          <div className="mt-6 overflow-x-auto" role="region" aria-label="Sample lab results" tabIndex={0}><table className="numeric w-full min-w-[540px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-hairline-strong text-left text-ink-faint">
                <th className="py-2 font-normal">Test</th>
                <th className="py-2 font-normal">Result</th>
                <th className="py-2 font-normal">Units</th>
                <th className="py-2 font-normal">Reference</th>
                <th className="py-2 font-normal">Flag</th>
              </tr>
            </thead>
            <tbody>
              {labPanel.rows.map((row) => (
                <tr key={row.test} className="border-b border-hairline">
                  <td className="py-2 text-ink">{row.test}</td>
                  <td className="py-2 text-ink">{row.value}</td>
                  <td className="py-2 text-ink-soft">{row.unit}</td>
                  <td className="py-2 text-ink-soft">{row.range}</td>
                  <td className="py-2 font-semibold text-ink">{row.flag && "H"}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
        <figcaption className="mt-4 text-[12px] leading-relaxed text-ink-faint">Synthetic preview. Extracted values require review before entering the chart.</figcaption>
      </figure>
    </Page>
  );
}
