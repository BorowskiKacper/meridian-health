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

/** Questions the phone can answer. Chart review stays on the web app. */
export const STARTERS = ["Are screenings up to date?", "What does the guideline recommend?"] as const;

export const WEB_HANDOFF = "Open the web app to review the chart and approve changes.";

export const MODES: { id: ChatMode; label: string; hint: string }[] = [
  { id: "auto", label: "Auto", hint: "Routes each request to the right agent" },
  { id: "chart", label: "Chart", hint: "Chart changes continue on the web app" },
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

/** Questions stay in the thread. Chart updates and other chart work point to the web app. */
export function phoneReply(result: Pick<DoctorRequest, "route" | "answer" | "suggestions">): {
  text: string;
  answer: Answer | null;
} {
  const answer = result.answer?.text ? result.answer : null;
  const chartWork = result.route === "chart_update" || (result.suggestions.length > 0 && result.route !== "clinical_question");
  if (answer && !chartWork) return { text: answer.text, answer };
  if (answer && chartWork) return { text: `${answer.text}\n\n${WEB_HANDOFF}`, answer };
  return { text: WEB_HANDOFF, answer: null };
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
