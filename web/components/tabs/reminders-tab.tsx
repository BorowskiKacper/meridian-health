"use client";

import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Page, PageHeader, Section } from "@/components/system/primitives";

const statusLabel = { scheduled: "Scheduled", due: "Due", sent: "Sent" } as const;

export function RemindersTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const sms = useStore((s) => s.sms[patientId]);
  const runReminders = useStore((s) => s.runReminders);
  const optOut = useStore((s) => s.optOut);
  if (!patient) return null;

  return (
    <Page>
      <PageHeader eyebrow={patient.name} title="Reminders">
        Screening and follow-up reminders. Due reminders go out by SMS on a schedule. That job is plain code, not AI.
      </PageHeader>

      <Section title="Schedule">
        <ul className="divide-y divide-hairline border-t border-hairline">
          {patient.reminders.map((r) => (
            <li key={r.id} className="flex items-baseline gap-6 py-4">
              <div className="min-w-0 flex-1">
                <p className="font-serif text-[18px] text-jade-900">{r.title}</p>
                <p className="mt-1 text-[13px] text-ink-soft">{r.detail}</p>
              </div>
              <span className={r.status === "due" ? "text-[13px] font-semibold text-ink" : "text-[13px] text-ink-faint"}>
                {statusLabel[r.status]}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="SMS">
        <div className="flex flex-wrap gap-2">
          <Button className="rounded-full px-4" onClick={() => runReminders(patientId)}>
            Run on a simulated date
          </Button>
          <Button variant="outline" className="rounded-full px-4" disabled={!patient.smsOptIn} onClick={() => optOut(patientId)}>
            Patient replies STOP
          </Button>
        </div>
        <div className="mt-6 max-w-md rounded-2xl rounded-bl-sm bg-ivory px-4 py-3 text-[14px] text-ink">
          {sms ?? (patient.smsOptIn ? "No message sent yet." : "SMS is off for this patient.")}
        </div>
        <p className="mt-3 text-[12px] text-ink-faint">Messages never include health details. A real send goes through Twilio.</p>
      </Section>
    </Page>
  );
}
