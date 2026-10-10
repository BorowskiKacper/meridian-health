"use client";

import { formatDate, initials, patientHue } from "@/lib/data";
import { useStore } from "@/lib/store";
import type { Allergy, Patient, WorkTab } from "@/lib/types";

const SEVERE = new Set(["severe", "anaphylaxis"]);

export function PatientBanner({ tab }: { tab: WorkTab }) {
  const patient = useStore((s) => s.patients[tab.patientId]);
  const openTab = useStore((s) => s.openTab);
  if (!patient) return null;

  const activeProblems = patient.problems.filter((p) => p.status === "active").length;
  const activeMeds = patient.medications.filter((m) => m.status === "active").length;
  const nextDue = [...patient.reminders].sort((a, b) => a.dueOn.localeCompare(b.dueOn)).find((r) => r.status === "due" || r.status === "sent");
  const hue = patientHue(patient.id);

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-hairline bg-ivory px-8 py-2.5 text-[13px]">
      <span className="flex items-center gap-2.5">
        <span
          aria-hidden
          className="grid size-7 place-items-center rounded-full text-[11px] font-semibold text-jade-900"
          style={{ background: hue }}
        >
          {initials(patient.name)}
        </span>
        <span>
          <span className="font-semibold text-jade-900">{patient.name}</span>
          <span className="ml-2 text-ink-faint">
            {patient.age} {patient.sex} · {patient.mrn}
            {patient.dob ? ` · ${formatDate(patient.dob)}` : ""}
          </span>
        </span>
      </span>

      <AllergyList allergies={patient.allergies} />

      <span className="ml-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-ink-soft">
        <BannerLink onClick={() => openTab("body", patient.id)} label={`${activeProblems} active problem${activeProblems === 1 ? "" : "s"}`} />
        <BannerLink onClick={() => openTab("body", patient.id)} label={`${activeMeds} medication${activeMeds === 1 ? "" : "s"}`} />
        {patient.pendingCount > 0 && (
          <BannerLink onClick={() => openTab("queue", patient.id)} label={`${patient.pendingCount} pending approval${patient.pendingCount === 1 ? "" : "s"}`} accent />
        )}
        {nextDue && <BannerLink onClick={() => openTab("reminders", patient.id)} label={`${nextDue.title} · ${nextDue.status === "due" ? "due" : "reminded"}`} />}
        {patient.coverage && (
          <span className="text-ink-faint">
            {patient.coverage.payer} {patient.coverage.plan}
            {patient.coverage.active ? "" : " · inactive"}
          </span>
        )}
      </span>
    </div>
  );
}

function BannerLink({ onClick, label, accent }: { onClick: () => void; label: string; accent?: boolean }) {
  return (
    <button type="button" onClick={onClick} className={accent ? "font-semibold text-jade-700 hover:text-jade-900" : "hover:text-ink"}>
      {label}
    </button>
  );
}

function AllergyList({ allergies }: { allergies: Allergy[] }) {
  const recorded = allergies.filter((a) => a.category !== "nkda");
  if (!recorded.length) {
    const verified = allergies.some((a) => a.category === "nkda");
    return <span className="text-ink-faint">{verified ? "No known drug allergies" : "Allergies not recorded"}</span>;
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5" aria-label="Allergies">
      {recorded.map((allergy) => {
        const severe = SEVERE.has(allergy.severity);
        return (
          <span
            key={allergy.id}
            title={`${allergy.category} · ${allergy.reaction} · recorded ${allergy.recordedOn ?? "unknown"}`}
            className={
              severe
                ? "rounded-full bg-critical/10 px-2 py-0.5 font-semibold text-critical"
                : "rounded-full bg-watch/15 px-2 py-0.5 text-watch"
            }
          >
            {allergy.substance}
            <span className="ml-1 font-normal opacity-75">{allergy.reaction}</span>
          </span>
        );
      })}
    </span>
  );
}

/** Used by the tab strip to show whose chart a tab belongs to. */
export function patientOf(patient: Patient | undefined) {
  return patient?.name.split(" ").at(-1);
}
