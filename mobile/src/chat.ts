import type { Answer, DoctorRequest, Suggestion } from "./types";

export type ChatRoute = "chart" | "research" | "screening";
export type ChatMode = "auto" | ChatRoute;

export type DoctorTurn = { id: string; role: "doctor"; text: string };

export type AgentTurn = {
  id: string;
  role: "agent";
  text: string;
  pending: boolean;
  route?: ChatRoute;
  suggestions: Suggestion[];
  answer: Answer | null;
  audioBase64: string | null;
};

export type Turn = DoctorTurn | AgentTurn;

export type ChatConversation = {
  id: string;
  patientId: string;
  title: string;
  messages: Turn[];
};

/** Same prompts as the web assistant, without workspace commands such as opening the timeline. */
export const STARTERS = ["Are screenings up to date?", "What is on the chart?"] as const;

export const MODES: { id: ChatMode; label: string; hint: string }[] = [
  { id: "auto", label: "Auto", hint: "Routes each request to the right agent" },
  { id: "chart", label: "Chart", hint: "Dictation becomes chart changes to approve" },
  { id: "research", label: "Ask", hint: "Clinical questions, answered with citations" },
  { id: "screening", label: "Screening", hint: "Reviews screenings and reminders" },
];

const ROUTE_LABEL: Record<ChatRoute, string> = {
  chart: "Chart",
  research: "Ask",
  screening: "Screening",
};

export function patientMrn(id: string): string {
  return `R-${id.replaceAll("-", "").slice(0, 6).toUpperCase()}`;
}

export function chatRoute(route: string): ChatRoute | null {
  if (route === "chart_update") return "chart";
  if (route === "clinical_question") return "research";
  if (route === "check_screenings") return "screening";
  return null;
}

export function chatRouteLabel(route: ChatRoute): string {
  return ROUTE_LABEL[route];
}

export function replyText(result: Pick<DoctorRequest, "answer" | "suggestions">): string {
  if (result.answer?.text) return result.answer.text;
  const count = result.suggestions.length;
  if (count) {
    return `Drafted ${count} chart change${count === 1 ? "" : "s"}. Nothing is written until you approve.`;
  }
  return "Nothing new was proposed.";
}

export function formatPatch(patch: Record<string, unknown> | null | undefined): string | undefined {
  if (!patch || !Object.keys(patch).length) return undefined;
  return Object.entries(patch)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
    .join(", ");
}

export function actionDetail(suggestion: Suggestion): string {
  const kind = suggestion.kind.replaceAll("_", " ");
  const table = suggestion.target_table.replaceAll("_", " ");
  return `${kind} · ${table}`;
}

export function confidenceText(value: number | null): string | undefined {
  if (value == null || !Number.isFinite(value)) return undefined;
  return `${Math.round(value * 100)}%`;
}
