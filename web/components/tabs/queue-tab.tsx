"use client";

import { useShallow } from "zustand/react/shallow";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { ActionCard } from "@/components/agent/action-card";
import { Page, PageHeader, Section } from "@/components/system/primitives";

export function QueueTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const actions = useStore(useShallow((s) => s.actions.filter((a) => a.patientId === patientId)));
  const audit = useStore(useShallow((s) => s.audit.filter((a) => a.patientId === patientId)));
  const approve = useStore((s) => s.approve);
  if (!patient) return null;

  const pending = actions.filter((a) => a.status === "pending");
  const decided = actions.filter((a) => a.status !== "pending").reverse();

  return (
    <Page>
      <PageHeader
        eyebrow={patient.name}
        title="Approvals"
        actions={
          pending.length > 1 && pending.every((a) => a.payload.kind !== "chart_change") && (
            <Button className="rounded-md px-4" onClick={() => pending.forEach((a) => approve(a.id))}>
              Approve all {pending.length}
            </Button>
          )
        }
      >
        Review proposed changes before they enter the chart.
      </PageHeader>

      <Section title={`Waiting · ${pending.length}`}>
        {pending.length ? (
          <div className="grid gap-5">
            {pending.map((action) => (
              <ActionCard key={action.id} action={action} detailed />
            ))}
          </div>
        ) : (
          <p className="text-[14px] text-ink-faint">Nothing is waiting for you.</p>
        )}
      </Section>

      {decided.length > 0 && (
        <details className="mt-8 border-t border-hairline pt-4">
          <summary className="w-fit cursor-pointer text-[13px] font-medium text-jade-700">Previous decisions · {decided.length}</summary>
          <div className="mt-5 grid gap-5">
            {decided.map((action) => (
              <ActionCard key={action.id} action={action} detailed />
            ))}
          </div>
        </details>
      )}

      {audit.length > 0 && <details className="mt-8 border-t border-hairline pt-4">
        <summary className="w-fit cursor-pointer text-[13px] font-medium text-jade-700">Session activity · {audit.length}</summary>
          <ol className="mt-4 divide-y divide-hairline">
            {[...audit].reverse().map((row) => (
              <li key={row.id} className="grid gap-y-2 py-4 text-[13px] @min-[700px]:grid-cols-[6rem_1fr] @min-[700px]:gap-x-6">
                <span className="text-ink-faint">{row.action}</span>
                <span className="min-w-0 break-words leading-relaxed text-ink">{row.detail}</span>
              </li>
            ))}
          </ol>
      </details>}
    </Page>
  );
}
