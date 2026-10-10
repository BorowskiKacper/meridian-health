"use client";

import type { WorkTab } from "@/lib/types";
import { ConversationView } from "@/components/agent/conversation";
import { BodyTab } from "./body-tab";
import { LabTab } from "./lab-tab";
import { QueueTab } from "./queue-tab";
import { RegionTab } from "./region-tab";
import { RemindersTab } from "./reminders-tab";
import { ResearchTab } from "./research-tab";
import { TimelineTab } from "./timeline-tab";

export function TabContent({ tab }: { tab: WorkTab }) {
  switch (tab.kind) {
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
    case "chat":
      return <ConversationView conversationId={tab.refId!} wide />;
  }
}
