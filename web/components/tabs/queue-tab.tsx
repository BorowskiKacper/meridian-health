"use client";

import { useShallow } from "zustand/react/shallow";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { firstName } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { ActionCard } from "@/components/agent/action-card";
import { Page, PageHeader, Section } from "@/components/system/primitives";

export function QueueTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const actions = useStore(useShallow((s) => s.actions.filter((a) => a.patientId === patientId)));
  const audit = useStore(useShallow((s) => s.audit.filter((a) => a.patientId === patientId)));
  const approveSelected = useStore((s) => s.approveSelected);
  const [selected, setSelected] = useState<string[]>([]);
  const busy = useStore((s) => s.actions.some((a) => a.patientId === patientId && s.approvingIds.includes(a.id)));
  if (!patient) return null;

  const pending = actions.filter((a) => a.status === "pending");
  const decided = actions.filter((a) => a.status !== "pending").reverse();
  const reviewed = selected.filter((id) => pending.some((a) => a.id === id));

  return (
    <Page>
      <PageHeader
        eyebrow={patient.name}
        title={`${firstName(patient.name)}’s Approvals`}
        actions={
          reviewed.length > 0 && (
            <Button disabled={busy} className="rounded-md px-4" onClick={async () => { if (await approveSelected(reviewed)) setSelected([]); }}>
              {busy ? "Approving…" : `Approve ${reviewed.length} reviewed change${reviewed.length === 1 ? "" : "s"}`}
            </Button>
          )
        }
      >
        Compare each proposal with the recorded chart. Approving saves chart changes; it does not sign a visit or submit a prescription.
      </PageHeader>

      <Section title={`Waiting · ${pending.length}`}>
        {pending.length ? (
          <div className="grid gap-5">
            {pending.map((action) => (
              <div key={action.id}><ActionCard action={action} detailed /><label className="mt-3 flex items-center gap-2 text-[12px] text-ink-soft"><input type="checkbox" className="size-4 accent-jade-600" disabled={busy} checked={reviewed.includes(action.id)} onChange={(e) => setSelected((ids) => e.target.checked ? [...ids, action.id] : ids.filter((id) => id !== action.id))} />Reviewed “{action.title}” for batch approval</label></div>
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
