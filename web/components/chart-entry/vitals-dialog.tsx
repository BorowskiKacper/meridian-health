"use client";

import { useRef, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Plus, X } from "lucide-react";
import { EntryForm, Field, entryInput, localDate, startChartEntry, useEntryPending } from "./entry-form";

const FIELDS = [
  ["systolic", "Systolic BP (mmHg)"],
  ["diastolic", "Diastolic BP (mmHg)"],
  ["pulse", "Heart rate (beats/min)"],
  ["respiratory_rate", "Respiratory rate (breaths/min)"],
  ["temperature_f", "Body temperature (°F)"],
] as const;

// Blood pressure is only usable as a pair, so each half becomes required once the other has a value.
const pairedWith = (key: string, v: Record<string, string>) => key === "systolic" ? v.diastolic !== "" : key === "diastolic" ? v.systolic !== "" : false;

export function VitalsDialog({ patientId }: { patientId: string }) {
  const [open, setOpen] = useState(false);
  const pending = useEntryPending(patientId, "vitals");
  const first = useRef<HTMLInputElement>(null);
  return <Dialog.Root open={open} onOpenChange={(next) => {
    // Never dismiss mid-save: the result must stay visible so it is not lost or retried blind.
    if (pending) return;
    if (next) startChartEntry(patientId, "vitals");
    setOpen(next);
  }}>
    <Dialog.Trigger className="inline-flex items-center gap-1.5 rounded-md bg-jade-900 px-3.5 py-2 text-[13px] font-medium text-white shadow-sm hover:bg-jade-700"><Plus aria-hidden className="size-4" />Record vitals</Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-[70] bg-ink/25" />
      <Dialog.Popup initialFocus={first} className="fixed top-1/2 left-1/2 z-[80] flex max-h-[calc(100dvh_-_3rem)] w-[calc(100%_-_2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border border-hairline-strong bg-clinical-surface shadow-lg">
        <div className="flex items-start justify-between gap-5 px-5 pt-5">
          <div><Dialog.Title className="font-sans text-[17px] font-semibold">Record vitals</Dialog.Title><Dialog.Description className="mt-1 text-[13px] leading-relaxed text-ink-soft">Every field is optional. Blank time means now; blood pressure needs both numbers.</Dialog.Description></div>
          <Dialog.Close aria-label="Close record vitals" disabled={pending} className="grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-jade-50 disabled:opacity-50"><X className="size-4" /></Dialog.Close>
        </div>
        <div className="@container overflow-y-auto px-5 pt-5 pb-5">
          <EntryForm embedded patientId={patientId} title="Record vitals" path="vitals" onSaved={() => setOpen(false)}
            initial={{ observed_at: localDate(), ...Object.fromEntries(FIELDS.map(([key]) => [key, ""])) }}
            build={(v) => ({
              observed_at: new Date(v.observed_at || localDate()).toISOString(),
              ...Object.fromEntries(FIELDS.map(([key]) => [key, v[key] === "" ? null : Number(v[key])])),
            })}>{(v, change) => <>
              <Field label="Measured at (local time)"><input ref={first} className={entryInput} type="datetime-local" value={v.observed_at} onChange={(e) => change("observed_at", e.target.value)} /></Field>
              {FIELDS.map(([key, label]) => <Field key={key} label={label}><input className={entryInput} type="number" inputMode="decimal" min="0.01" step="any" required={pairedWith(key, v)} value={v[key]} onChange={(e) => change(key, e.target.value)} /></Field>)}
            </>}</EntryForm>
        </div>
      </Dialog.Popup>
    </Dialog.Portal>
  </Dialog.Root>;
}
