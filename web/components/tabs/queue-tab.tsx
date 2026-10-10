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
          pending.length > 1 && (
            <Button className="rounded-full px-4" onClick={() => pending.forEach((a) => approve(a.id))}>
              Approve all {pending.length}
            </Button>
          )
        }
      >
        Every search, new tab, and chart change the assistant proposes waits here. Nothing happens until you approve it.
      </PageHeader>

      <Section title={`Waiting · ${pending.length}`}>
        {pending.length ? (
          <div className="grid gap-3">
            {pending.map((action) => (
              <ActionCard key={action.id} action={action} detailed />
            ))}
          </div>
        ) : (
          <p className="text-[14px] text-ink-faint">Nothing is waiting for you.</p>
        )}
      </Section>

      {decided.length > 0 && (
        <Section title="Decided">
          <div className="grid gap-3">
            {decided.map((action) => (
              <ActionCard key={action.id} action={action} detailed />
            ))}
          </div>
        </Section>
      )}

      <Section title="Audit log">
        {audit.length ? (
          <ol className="divide-y divide-hairline border-t border-hairline">
            {[...audit].reverse().map((row) => (
              <li key={row.id} className="flex gap-6 py-2.5 text-[13px]">
                <span className="w-20 shrink-0 text-ink-faint">{row.action}</span>
                <span className="text-ink">{row.detail}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[14px] text-ink-faint">No decisions yet.</p>
        )}
      </Section>
    </Page>
  );
}
