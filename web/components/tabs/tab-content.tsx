"use client";

import type { WorkTab } from "@/lib/types";
import { BodyTab } from "./body-tab";
import { LabTab } from "./lab-tab";
import { QueueTab } from "./queue-tab";
import { RegionTab } from "./region-tab";
import { RemindersTab } from "./reminders-tab";
import { ResearchTab } from "./research-tab";
import { TimelineTab } from "./timeline-tab";
import { OverviewTab } from "./overview-tab";
import { VitalsTab } from "./vitals-tab";
import { ChartListsTab } from "./chart-lists-tab";
import { VisitTab } from "./visit-tab";
import { HistoryTab } from "./history-tab";

export function TabContent({ tab }: { tab: WorkTab }) {
  switch (tab.kind) {
    case "history":
      return <HistoryTab key={tab.id} patientId={tab.patientId} />;
    case "visit":
      return <VisitTab key={tab.id} patientId={tab.patientId} />;
    case "overview":
      return <OverviewTab key={tab.id} patientId={tab.patientId} />;
    case "vitals":
      return <VitalsTab key={tab.id} patientId={tab.patientId} />;
    case "problems":
    case "medications":
    case "allergies":
      return <ChartListsTab key={tab.id} patientId={tab.patientId} kind={tab.kind} />;
    case "body":
      return <BodyTab key={tab.id} patientId={tab.patientId} />;
    case "region":
      return <RegionTab patientId={tab.patientId} findingId={tab.refId!} />;
    case "timeline":
      return <TimelineTab patientId={tab.patientId} />;
    case "queue":
      return <QueueTab patientId={tab.patientId} />;
    case "research":
      return <ResearchTab researchId={tab.refId!} />;
    case "lab":
      return <LabTab patientId={tab.patientId} />;
    case "reminders":
      return <RemindersTab patientId={tab.patientId} />;
  }
}
