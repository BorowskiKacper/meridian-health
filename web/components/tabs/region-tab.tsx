"use client";

import { ArrowUpRight } from "lucide-react";
import { formatDate, formatMonth, kindLabel, severityLabel } from "@/lib/data";
import { useStore } from "@/lib/store";
import { Page, PageHeader, Section, SeverityDot } from "@/components/system/primitives";
import { TrendChart } from "@/components/charts/trend-chart";

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
        <span className="flex items-center gap-2">
          <SeverityDot severity={finding.severity} />
          {finding.condition}
        </span>
      </PageHeader>

      <p className="mt-8 max-w-2xl font-serif text-[19px] leading-relaxed text-jade-900">{finding.note}</p>
      <p className="mt-3 text-[13px] text-ink-faint">
        {severityLabel[finding.severity]} · on the chart since {finding.when ?? "today"} · {finding.structureId}
      </p>

      {finding.trends.length > 0 && (
        <Section title="Trends">
          <div className="grid gap-4">
            {finding.trends.map((trend) => (
              <TrendChart key={trend.name} trend={trend} markers={markers} />
            ))}
          </div>
        </Section>
      )}

      <div className="grid gap-x-16 md:grid-cols-2">
        <Section title="Problems">
          {finding.problems.length ? (
            <dl className="divide-y divide-hairline">
              {finding.problems.map((problem) => (
                <div key={problem.id} className="flex justify-between gap-6 py-2.5 text-[14px]">
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
                <li key={m.id} className="flex justify-between gap-6 py-2.5 text-[14px]">
                  <span className={m.status === "active" ? "text-ink" : "text-ink-faint line-through"}>
                    {m.name} {m.dose} {m.route} {m.frequency}
                  </span>
                  <span className="shrink-0 text-right text-[12px] text-ink-faint">
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

      <div className="grid gap-x-16 md:grid-cols-2">
        <Section title="Latest results">
          {finding.observations.length ? (
            <dl className="divide-y divide-hairline">
              {finding.observations.map((o) => (
                <div key={o.label} className="flex justify-between gap-6 py-2.5 text-[14px]">
                  <dt className="text-ink-soft">{o.label}</dt>
                  <dd className="text-right">
                    <span className="numeric text-ink">{o.value}</span>
                    {o.at && <span className="block text-[12px] text-ink-faint">{formatDate(o.at)}</span>}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-[14px] text-ink-faint">No results on this region</p>
          )}
        </Section>
        <Section title="Family history">
          {patient.family.length ? (
            <ul className="space-y-1.5 text-[14px] text-ink">
              {patient.family.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          ) : (
            <p className="text-[14px] text-ink-faint">None recorded</p>
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
        <Section title="Notes">
          <ul className="space-y-3 text-[14px] leading-relaxed text-ink">
            {notes.map((n) => (
              <li key={n.id}>
                <span className="mr-2 text-[12px] text-ink-faint">{formatDate(n.at)}</span>
                {n.text}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </Page>
  );
}
