import prompts from "../../backend/app/demo/prompts.json";
import type { RequestRoute } from "./api";

export function demoPrompts(patientId: string | null | undefined, mode?: RequestRoute) {
  return prompts.filter((prompt) => prompt.patient_id === patientId && (patientId === null || prompt.route === mode));
}

export function demoPrompt(patientId: string | null, text: string) {
  return prompts.find((prompt) => prompt.patient_id === patientId && prompt.text === text);
}
