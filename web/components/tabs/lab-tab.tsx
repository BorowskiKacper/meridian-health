"use client";

import { labPanel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Page, PageHeader } from "@/components/system/primitives";

export function LabTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const extracted = useStore((s) => s.actions.some((a) => a.patientId === patientId && a.source.startsWith("Lab photo")));
  const extractLab = useStore((s) => s.extractLab);
  if (!patient) return null;

  return (
    <Page>
      <PageHeader
        eyebrow={`${patient.name} · Photographed document`}
        title="Lab report"
        actions={
          <Button className="rounded-full px-4" disabled={extracted} onClick={() => extractLab(patientId)}>
            {extracted ? "Drafts sent to the assistant" : "Extract values"}
          </Button>
        }
      >
        A photo of a paper report. Extraction drafts the flagged values as chart changes for you to approve.
      </PageHeader>

      <figure className="mt-10 rounded-lg border border-hairline bg-ivory p-10">
        <div className="mx-auto max-w-2xl bg-white px-10 py-9 shadow-[0_1px_3px_rgb(0_0_0/0.06)]">
          <div className="flex items-baseline justify-between border-b border-ink/80 pb-3">
            <p className="font-serif text-[18px] text-ink">{labPanel.lab}</p>
            <p className="text-[12px] text-ink-soft">{labPanel.collected}</p>
          </div>
          <p className="mt-4 text-[13px] text-ink-soft">
            {labPanel.title} · Patient: {patient.name}
          </p>
          <table className="numeric mt-5 w-full text-[13px]">
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
          </table>
        </div>
        <figcaption className="mt-4 text-center text-[12px] text-ink-faint">Filler document for the demo</figcaption>
      </figure>
    </Page>
  );
}
