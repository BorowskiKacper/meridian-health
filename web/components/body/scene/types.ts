import type { StandardView } from "@authorod/svitylo-3d-anatomy-atlas/core";

export type Severity = "critical" | "watch" | "clear";
export type Tool = "orbit" | "probe" | "measure" | "mark";
export type CutAxis = "x" | "y" | "z";

export interface SceneSnapshot {
  status: "loading" | "ready" | "error";
  progress: number;
  loadingText: string;
  error: string | null;
  tool: Tool;
  impacts: boolean;
  cutaway: boolean;
  cutAxis: CutAxis;
  cutT: number;
  cutCaption: string;
  hud: string;
  activeId: string;
  walking: boolean;
  measures: number;
  notes: number;
}

export interface LookupHit {
  id: string;
  label: string;
  latin?: string;
}

export const initialSnapshot: SceneSnapshot = {
  status: "loading",
  progress: 0.08,
  loadingText: "Opening the anatomy",
  error: null,
  tool: "orbit",
  impacts: true,
  cutaway: false,
  cutAxis: "y",
  cutT: 0.5,
  cutCaption: "",
  hud: "",
  activeId: "",
  walking: false,
  measures: 0,
  notes: 0,
};

export interface SceneFinding {
  id: string;
  structureId: string;
  title: string;
  severity: Severity;
  /** Preferred outward direction in patient space: +X is the patient's left, +Y up, +Z anterior. */
  outward: [number, number, number];
  view: StandardView;
  impact?: boolean;
}

/** Pin colours tuned for the dark stage; the page itself uses the muted severity tokens. */
export const severityColor: Record<Severity, string> = {
  critical: "#e2735f",
  watch: "#e3b45c",
  clear: "#7fb8a4",
};

export const severityLabel: Record<Severity, string> = {
  critical: "Critical",
  watch: "Watch",
  clear: "Clear",
};
