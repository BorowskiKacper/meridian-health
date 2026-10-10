"use client";

import { ArrowUpRight } from "lucide-react";
import { formatDate, formatMonth, kindLabel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Page, PageHeader, Section, SeverityDot } from "@/components/system/primitives";
import { MeasurementList } from "@/components/charts/measurement-list";

/** Problems that implicate another region a primary care visit should look at. */
const RELATED: Record<string, { regionKey: string; why: string }[]> = {
  pancreas: [
    { regionKey: "kidney", why: "Diabetic kidney disease: eGFR and urine albumin yearly" },
    { regionKey: "heart", why: "Cardiovascular risk: blood pressure and lipids" },
  ],
  kidney: [
    { regionKey: "heart", why: "Blood pressure control slows CKD progression" },
    { regionKey: "pancreas", why: "Glycaemic control slows CKD progression" },
  ],
  heart: [{ regionKey: "kidney", why: "Hypertension and CKD progress together" }],
};

export function RegionTab({ patientId, findingId }: { patientId: string; findingId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const openTab = useStore((s) => s.openTab);
  const newConversation = useStore((s) => s.newConversation);
  const send = useStore((s) => s.send);
  const finding = patient?.findings.find((f) => f.id === findingId);
  if (!patient || !finding) return null;
  const notes = patient.notes.filter((n) => n.findingId === finding.id && n.kind !== "medication");
  const meds = patient.medications.filter((m) => m.regionKey === finding.regionKey);
  const markers = meds.filter((m) => m.start).map((m) => ({ at: m.start!, label: m.name }));
  const related = (RELATED[finding.regionKey] ?? []).filter((item) => patient.findings.some((f) => f.regionKey === item.regionKey));

  return (
    <Page>
      <PageHeader
        eyebrow={`${patient.name} · ${kindLabel[finding.kind]}`}
        title={finding.title}
        actions={
          <button
            type="button"
            onClick={() => {
              newConversation(patientId);
              send(`What does the chart say about ${finding.title.toLowerCase()} for this patient?`);
            }}
            className="flex h-9 items-center gap-1.5 rounded-md border border-hairline-strong bg-white px-3.5 text-[13px] text-jade-900 hover:bg-jade-50"
          >
            Ask about this
            <ArrowUpRight className="size-3.5" />
          </button>
        }
      >
        Related diagnoses, medications and measurements.
      </PageHeader>

      <Section title="Measurements"><MeasurementList series={finding.trends} markers={markers} /></Section>

      <div className="grid gap-x-8 @min-[900px]:grid-cols-2">
        <Section title="Problems">
          {finding.problems.length ? (
            <dl className="divide-y divide-hairline">
              {finding.problems.map((problem) => (
                <div key={problem.id} className="flex flex-wrap justify-between gap-x-6 gap-y-2 py-4 text-[14px]">
                  <dt className="text-ink">{problem.name}</dt>
                  <dd className="text-right text-ink-soft">
                    <span className={problem.status === "active" ? "text-ink" : ""}>{problem.status}</span>
                    {problem.onset && <span className="block text-[12px] text-ink-faint">since {formatMonth(problem.onset)}</span>}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-[14px] text-ink-faint">No problem charted; results only</p>
          )}
        </Section>
        <Section title="Medications">
          {meds.length ? (
            <ul className="divide-y divide-hairline">
              {meds.map((m) => (
                <li key={m.id} className="py-4 text-[14px]">
                  <span className={m.status === "active" ? "text-ink" : "text-ink-faint line-through"}>
                    <strong className="font-semibold">{m.name}</strong> {m.dose}<span className="mt-1.5 block text-[13px] text-ink-soft">{m.route} · {m.frequency}</span>
                  </span>
                  <span className="mt-2 block text-[12px] text-ink-faint">
                    {m.status === "active" ? "since" : "stopped · started"} {m.start ? formatMonth(m.start) : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[14px] text-ink-faint">None charted</p>
          )}
        </Section>
      </div>

      {related.length > 0 && (
        <Section title="Look at together">
          <ul className="divide-y divide-hairline border-t border-hairline">
            {related.map((item) => {
              const target = patient.findings.find((f) => f.regionKey === item.regionKey)!;
              return (
                <li key={item.regionKey}>
                  <button
                    type="button"
                    onClick={() => openTab("region", patientId, target.id)}
                    className="group flex w-full items-baseline gap-3 py-3 text-left"
                  >
                    <SeverityDot severity={target.severity} />
                    <span className="min-w-0 flex-1">
                      <span className="font-serif text-[16px] text-jade-900 group-hover:text-jade-600">{target.title}</span>
                      <span className="mt-0.5 block text-[13px] text-ink-soft">{item.why}</span>
                    </span>
                    <ArrowUpRight className="size-3.5 text-ink-faint" />
                  </button>
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      {notes.length > 0 && (
        <details className="mt-8 border-t border-hairline pt-4"><summary className="w-fit cursor-pointer text-[13px] font-medium text-jade-700">Related notes · {notes.length}</summary>
          <ul className="space-y-3 text-[14px] leading-relaxed text-ink">
            {notes.map((n) => (
              <li key={n.id}>
                <span className="mr-2 text-[12px] text-ink-faint">{formatDate(n.at)}</span>
                {n.text}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Page>
  );
}
