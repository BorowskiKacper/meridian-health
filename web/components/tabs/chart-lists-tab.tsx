"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { formatDate, firstName } from "@/lib/data";
import { allergySummary } from "@/lib/clinical";
import { Page, PageHeader } from "@/components/system/primitives";
import { ListEntry } from "@/components/chart-entry/list-entry";
import { ReviewPanel } from "@/components/chart-entry/review-panel";
import { EntryForm, Field, entryButton, entryInput, localDate, startChartEntry } from "@/components/chart-entry/entry-form";
import type { Allergy, Medication } from "@/lib/types";

export function ChartListsTab({ patientId, kind }: { patientId: string; kind: "problems" | "medications" | "allergies" }) {
  const patient = useStore((state) => state.patients[patientId]);
  const openTab = useStore((state) => state.openTab);
  const showHistory = useStore((state) => kind !== "allergies" && !!state.chartHistory[`${patientId}:${kind}`]);
  const setChartHistory = useStore((state) => state.setChartHistory);
  const [editingId, setEditingId] = useState<string | null>(null);
  if (!patient) return null;
  const title = kind === "problems" ? "Problem list" : kind === "medications" ? "Medications" : "Allergies & intolerances";
  const medications = patient.medications.filter((record) => showHistory || record.status === "active");
  const problems = patient.problems.filter((record) => showHistory || record.status !== "resolved");

  const editor = (record: Medication | Allergy) => editingId === record.id && (
    "category" in record && record.category === "nkda" ? <EntryForm patientId={patientId} title="Resolve no-known-drug-allergy record" path={`allergies/${record.id}/status`} method="PUT" initial={{}} build={() => ({ status: "inactive" })} onSaved={() => setEditingId(null)} defaultOpen>{() => <p className="text-[13px] leading-relaxed text-ink-soft @min-[700px]:col-span-2">Save to mark this no-known-drug-allergy assertion inactive. The original assertion remains in the history.</p>}</EntryForm> : <ListEntry patientId={patientId} kind={kind} record={record} onSaved={() => setEditingId(null)} />
  );
  const editButton = (record: Medication | Allergy) => <button type="button" className={`${entryButton} shrink-0`} aria-expanded={editingId === record.id} aria-label={editingId === record.id ? "Close editor" : "name" in record ? `Edit ${record.name}` : record.category === "nkda" ? "Resolve NKDA record" : `Edit ${record.substance}`} onClick={() => {
    if (editingId !== record.id) startChartEntry(patientId, `${kind}/${record.id}${"category" in record && record.category === "nkda" ? "/status" : ""}`);
    setEditingId(editingId === record.id ? null : record.id);
  }}>{editingId === record.id ? "Close editor" : "category" in record && record.category === "nkda" ? "Resolve record" : "Edit record"}</button>;

  return <Page>
    <PageHeader title={`${firstName(patient.name)}’s ${title}`}>
      {kind === "allergies" ? "Substances, reported reactions and recorded severity." : kind === "medications" ? "Recorded medication history and patient-reported use." : "Documented problems, status and onset dates."}
    </PageHeader>
    <ListEntry patientId={patientId} kind={kind} />
    {kind !== "allergies" && <label className="mt-7 flex w-fit items-center gap-2 text-[13px] text-ink-soft"><input type="checkbox" checked={showHistory} onChange={(event) => setChartHistory(patientId, kind, event.target.checked)} className="size-4 shrink-0 accent-jade-600" />{kind === "medications" ? "Include stopped and other records" : "Include resolved problems"}</label>}

    {kind === "allergies" ? <section aria-label={`Allergy records for ${patient.name}`} className="mt-7">
      <p className="mb-4 text-[13px] font-medium text-jade-900">Current status: {allergySummary(patient.allergies)}</p>
      <ul className="divide-y divide-hairline border-y border-hairline">{patient.allergies.map((record) => <li key={record.id} className="py-6">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
          <div className="min-w-0 flex-1 basis-56">
            <h2 className="font-sans text-[15px] font-semibold">{record.substance}</h2>
            {record.category !== "nkda" && <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">Reaction: {record.reaction || "Not recorded"}</p>}
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[12px] text-ink-soft">
              {record.category !== "nkda" && <span className={["severe", "anaphylaxis"].includes(record.severity) ? "font-semibold text-critical" : ""}>Severity: <span className="capitalize">{record.severity || "Not recorded"}</span></span>}
              <span className="capitalize">{record.status || "Status not recorded"}</span>
              <span className="capitalize">{record.category === "nkda" ? "Explicit drug-allergy history" : record.category}</span>
            </div>
            <p className="mt-2 text-[12px] text-ink-faint">Recorded {record.recordedOn ? formatDate(record.recordedOn) : "date not available"}</p>
          </div>
          {(record.category !== "nkda" || record.status === "active") && editButton(record)}
        </div>{editor(record)}
      </li>)}</ul>
      {!patient.allergies.length && <p className="py-6 text-[13px] text-ink-soft">No allergy records. This does not establish no known allergies.</p>}
    </section> : kind === "medications" ? <section aria-label={`Medication records for ${patient.name}`} className="mt-5">
      <ul className="divide-y divide-hairline border-y border-hairline">{medications.map((record) => <li key={record.id} className="py-6">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
          <div className="min-w-0 flex-1 basis-56">
            <h2 className="font-sans text-[15px] font-semibold">{record.name} <span className="ml-2 font-normal text-ink-soft">{record.dose || "Dose not recorded"}</span></h2>
            <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{record.route || "Route not recorded"} · {record.frequency || "Frequency not recorded"}</p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-faint"><span className="capitalize">{record.status}</span><span>Started {record.start ? formatDate(record.start) : "date not recorded"}</span></div>
          </div>{editButton(record)}
        </div>{editor(record)}
      </li>)}</ul>
      {!medications.length && <p className="py-6 text-[13px] text-ink-soft">No medication records in this view.</p>}
    </section> : <section aria-label={`Problem list for ${patient.name}`} className="mt-5">
      <ul className="divide-y divide-hairline border-y border-hairline">{problems.map((record) => <li key={record.id} className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 py-6">
        <div className="min-w-0 flex-1 basis-56"><h2 className="font-sans text-[15px] font-semibold">{record.name}</h2><div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-soft"><span className="capitalize">{record.status}</span><span>Onset {record.onset ? formatDate(record.onset) : "not recorded"}</span></div></div>
        <button type="button" className={entryButton} onClick={() => openTab("region", patientId, record.regionKey)}>Review details</button>
      </li>)}</ul>
      {!problems.length && <p className="py-6 text-[13px] text-ink-soft">No problems recorded in this view.</p>}
    </section>}

    {kind === "allergies" && !patient.allergies.some((record) => record.status === "active" && ["drug", "nkda"].includes(record.category)) && <EntryForm patientId={patientId} title="Record no known drug allergies" path="no-known-drug-allergies" initial={{ recorded_on: localDate().slice(0, 10), confirmed: "" }} build={(values) => ({ recorded_on: values.recorded_on, confirmed_with_patient: values.confirmed === "yes" })}>{(values, change) => <>
      <Field label="Reviewed on"><input className={entryInput} required type="date" value={values.recorded_on} onChange={(event) => change("recorded_on", event.target.value)} /></Field>
      <label className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-soft"><input className="mt-1 size-4 shrink-0 accent-jade-600" required type="checkbox" checked={values.confirmed === "yes"} onChange={(event) => change("confirmed", event.target.checked ? "yes" : "")} />The patient or caregiver reports no known drug allergies. This assertion does not cover food or environmental allergies.</label>
    </>}</EntryForm>}
    {kind !== "problems" && <ReviewPanel patientId={patientId} kind={kind} />}
  </Page>;
}
