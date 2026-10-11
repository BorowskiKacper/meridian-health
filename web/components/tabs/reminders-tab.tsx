"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { formatDate, firstName } from "@/lib/data";
import type { Reminder } from "@/lib/types";
import { Page, PageHeader } from "@/components/system/primitives";
import { EntryForm, Field, entryButton, entryInput, startChartEntry } from "@/components/chart-entry/entry-form";

const statusLabel = { scheduled: "Scheduled", due: "Due", sent: "Reminder sent", paused: "Paused", done: "Completed" } as const;

export function RemindersTab({ patientId }: { patientId: string }) {
  const patient = useStore((s) => s.patients[patientId]);
  const [editingId, setEditingId] = useState<string | null>(null);
  if (!patient) return null;
  const active = patient.reminders.filter((r) => r.status !== "done" && r.status !== "paused").sort((a, b) => a.dueOn.localeCompare(b.dueOn));
  const history = patient.reminders.filter((r) => r.status === "done" || r.status === "paused").sort((a, b) => b.dueOn.localeCompare(a.dueOn));

  const taskRow = (task: Reminder) => <li key={task.id} className="py-6">
    <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
      <div className="min-w-0 flex-1 basis-56">
        <h3 className="font-sans text-[15px] font-semibold leading-relaxed text-ink">{task.title}</h3>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px] text-ink-soft">
          <span>Due <time dateTime={task.dueOn}>{formatDate(task.dueOn)}</time></span>
          <span className={task.status === "due" ? "rounded bg-watch/10 px-2 py-0.5 font-medium text-watch" : ""}>{statusLabel[task.status]}</span>
        </div>
        {task.rule && <details className="mt-3 text-[12px] text-ink-faint">
          <summary className="w-fit cursor-pointer hover:text-jade-700">Task source</summary>
          <p className="mt-2 break-words leading-relaxed">Recorded source: {task.rule.source}</p>
        </details>}
      </div>
      <button type="button" className={`${entryButton} shrink-0`} aria-expanded={editingId === task.id} onClick={() => {
        if (editingId !== task.id) startChartEntry(patientId, `follow-up/${task.id}`);
        setEditingId(editingId === task.id ? null : task.id);
      }}>{editingId === task.id ? "Close editor" : "Update task"}</button>
    </div>
    {editingId === task.id && <EntryForm key={task.id} patientId={patientId} title="Update follow-up" path={`follow-up/${task.id}`} method="PUT" initial={{ due_on: task.dueOn, status: task.status === "sent" ? "scheduled" : task.status }} build={(values) => values} onSaved={() => setEditingId(null)} defaultOpen>{(values, change) => <>
      <Field label="Due date"><input className={entryInput} type="date" required value={values.due_on} onChange={(event) => change("due_on", event.target.value)} /></Field>
      <Field label="Task status"><select className={entryInput} value={values.status} onChange={(event) => change("status", event.target.value)}>{["scheduled", "due", "paused", "done"].map((status) => <option key={status} value={status}>{statusLabel[status as keyof typeof statusLabel]}</option>)}</select></Field>
      <p className="text-[12px] leading-relaxed text-ink-soft @min-[700px]:col-span-2">Mark Completed once this follow-up has been completed.</p>
    </>}</EntryForm>}
  </li>;

  return <Page>
    <PageHeader title={`${firstName(patient.name)}’s Follow-up`}>Screening and monitoring tasks on this chart.</PageHeader>
    <section className="mt-9" aria-label="Open follow-up tasks">
      <h2 className="mb-3 font-sans text-[13px] font-semibold text-ink-soft">Open tasks <span className="ml-2 font-normal text-ink-faint">{active.length}</span></h2>
      {active.length ? <ul className="divide-y divide-hairline border-y border-hairline">{active.map(taskRow)}</ul> : <p className="border-y border-hairline py-6 text-[13px] text-ink-soft">No open follow-up tasks recorded.</p>}
    </section>
    {history.length > 0 && <details className="mt-8">
      <summary className="w-fit cursor-pointer text-[13px] font-medium text-ink-soft hover:text-jade-700">Completed & paused <span className="ml-2 text-ink-faint">{history.length}</span></summary>
      <ul className="mt-4 divide-y divide-hairline border-y border-hairline">{history.map(taskRow)}</ul>
    </details>}
  </Page>;
}
