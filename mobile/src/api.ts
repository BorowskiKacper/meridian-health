import type {
  Answer,
  ApproveResult,
  Citation,
  DoctorRequest,
  ReminderReview,
  Suggestion,
} from "./types";

export const DOCTOR_ROLE = "doctor";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export type AudioPart = Blob | { uri: string; name: string; type: string };

export type DoctorInput = { text: string } | { audio: AudioPart };

export function apiBaseUrl(): string {
  const configured = process.env.EXPO_PUBLIC_API_URL;
  if (typeof configured === "string" && configured.trim()) {
    return configured.trim().replace(/\/$/, "");
  }
  return "https://hackknight-fall-26.onrender.com";
}

export function filenameForMime(mime: string): string {
  if (mime.includes("webm")) return "dictation.webm";
  if (mime.includes("wav")) return "dictation.wav";
  if (mime.includes("mpeg") || mime.includes("mp3")) return "dictation.mp3";
  if (mime.includes("mp4") || mime.includes("m4a") || mime.includes("aac")) {
    return "dictation.m4a";
  }
  return "dictation.audio";
}

export function buildDoctorRequest(patientId: string, input: DoctorInput): FormData {
  const body = new FormData();
  body.append("patient_id", patientId);
  if ("text" in input) {
    const text = input.text.trim();
    if (!text) {
      throw new ApiError(400, "validation_error", "Type a message or dictate.");
    }
    body.append("text", text);
    return body;
  }
  const audio = input.audio;
  if (typeof Blob !== "undefined" && audio instanceof Blob) {
    const type = audio.type || "application/octet-stream";
    body.append("audio", audio, filenameForMime(type));
    return body;
  }
  body.append("audio", audio as unknown as Blob);
  return body;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function expectString(value: unknown, label: string): string {
  if (typeof value !== "string") {
    throw new ApiError(200, "validation_error", `The API omitted ${label}.`);
  }
  return value;
}

function parseCitation(value: unknown): Citation {
  if (!isRecord(value)) {
    throw new ApiError(200, "validation_error", "The API returned a citation the client could not read.");
  }
  return {
    source_id: expectString(value.source_id, "citation source_id"),
    title: expectString(value.title, "citation title"),
    passage: expectString(value.passage, "citation passage"),
    locator: expectString(value.locator, "citation locator"),
    tier: expectString(value.tier, "citation tier"),
  };
}

function parseCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) return [];
  return value.map(parseCitation);
}

function parseObject(value: unknown): Record<string, unknown> | null {
  if (value == null) return null;
  if (!isRecord(value)) return null;
  return value;
}

export function parseSuggestion(value: unknown): Suggestion {
  if (!isRecord(value)) {
    throw new ApiError(200, "validation_error", "The API returned a suggestion the client could not read.");
  }
  const confidence = value.confidence;
  return {
    id: expectString(value.id, "suggestion id"),
    patient_id: typeof value.patient_id === "string" ? value.patient_id : "",
    request_id: typeof value.request_id === "string" ? value.request_id : null,
    kind: typeof value.kind === "string" ? value.kind : "",
    status: typeof value.status === "string" ? value.status : "",
    target_table: typeof value.target_table === "string" ? value.target_table : "",
    target_id: typeof value.target_id === "string" ? value.target_id : null,
    before: parseObject(value.before),
    after: parseObject(value.after),
    reason: typeof value.reason === "string" ? value.reason : "",
    confidence: typeof confidence === "number" ? confidence : null,
    citations: parseCitations(value.citations),
    validation_flags: Array.isArray(value.validation_flags)
      ? value.validation_flags.filter((flag): flag is string => typeof flag === "string")
      : [],
    source: typeof value.source === "string" ? value.source : "",
  };
}

function parseAnswer(value: unknown): Answer | null {
  if (value == null) return null;
  if (!isRecord(value)) {
    throw new ApiError(200, "validation_error", "The API returned an answer the client could not read.");
  }
  return {
    text: typeof value.text === "string" ? value.text : "",
    citations: parseCitations(value.citations),
  };
}

export function parseDoctorRequest(value: unknown): DoctorRequest {
  if (!isRecord(value)) {
    throw new ApiError(200, "validation_error", "The API returned a request the client could not read.");
  }
  const suggestions = value.suggestions;
  if (!Array.isArray(suggestions)) {
    throw new ApiError(200, "validation_error", "The API omitted suggestions.");
  }
  return {
    request_id: expectString(value.request_id, "request_id"),
    transcript: typeof value.transcript === "string" ? value.transcript : "",
    route: expectString(value.route, "route"),
    suggestions: suggestions.map(parseSuggestion),
    answer: parseAnswer(value.answer),
    spoken_text: typeof value.spoken_text === "string" ? value.spoken_text : null,
    audio_base64: typeof value.audio_base64 === "string" ? value.audio_base64 : null,
  };
}

export function parseSuggestionList(value: unknown): Suggestion[] {
  if (!isRecord(value) || !Array.isArray(value.suggestions)) {
    throw new ApiError(200, "validation_error", "The API omitted the suggestion list.");
  }
  return value.suggestions.map(parseSuggestion);
}

function parseReviewAnswer(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (isRecord(value) && typeof value.text === "string") return value.text;
  return null;
}

export function parseApproveResult(value: unknown): ApproveResult {
  if (!isRecord(value) || !isRecord(value.reminder_review)) {
    throw new ApiError(200, "validation_error", "The API omitted the reminder review.");
  }
  const review = value.reminder_review;
  const suggestions = Array.isArray(review.suggestions) ? review.suggestions.map(parseSuggestion) : [];
  const reminderReview: ReminderReview = {
    suggestions,
    answer: parseReviewAnswer(review.answer),
  };
  const approved = Array.isArray(value.approved) ? value.approved.map(parseSuggestion) : [];
  return { approved, reminder_review: reminderReview };
}

function errorFrom(status: number, payload: unknown): ApiError {
  if (
    isRecord(payload) &&
    isRecord(payload.error) &&
    typeof payload.error.code === "string" &&
    typeof payload.error.message === "string" &&
    payload.error.message.trim()
  ) {
    return new ApiError(status, payload.error.code, payload.error.message);
  }
  return new ApiError(status, "validation_error", "The API returned an error.");
}

async function requestJson(url: string, init: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(0, "validation_error", "Could not reach the API.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw errorFrom(response.status, payload);
  return payload;
}

function roleHeaders(json: boolean): HeadersInit {
  if (json) return { "X-Role": DOCTOR_ROLE, "Content-Type": "application/json" };
  return { "X-Role": DOCTOR_ROLE };
}

export function createClient(baseUrl: string) {
  const root = baseUrl.replace(/\/$/, "");
  return {
    sendRequest(patientId: string, input: DoctorInput): Promise<DoctorRequest> {
      return requestJson(`${root}/requests`, {
        method: "POST",
        headers: roleHeaders(false),
        body: buildDoctorRequest(patientId, input),
      }).then(parseDoctorRequest);
    },
    listPending(patientId: string): Promise<Suggestion[]> {
      const query = new URLSearchParams({ patient_id: patientId, status: "pending" });
      return requestJson(`${root}/suggestions?${query}`, {
        headers: roleHeaders(false),
      }).then(parseSuggestionList);
    },
    addToPlan(
      patientId: string,
      requestId: string,
      text: string,
      citations: Citation[],
    ): Promise<Suggestion> {
      return requestJson(`${root}/suggestions`, {
        method: "POST",
        headers: roleHeaders(true),
        body: JSON.stringify({
          patient_id: patientId,
          request_id: requestId,
          text,
          citations,
        }),
      }).then(parseSuggestion);
    },
    approve(suggestionIds: string[]): Promise<ApproveResult> {
      return requestJson(`${root}/suggestions/approve`, {
        method: "POST",
        headers: roleHeaders(true),
        body: JSON.stringify({ suggestion_ids: suggestionIds }),
      }).then(parseApproveResult);
    },
    reject(suggestionIds: string[], reason: string): Promise<Suggestion[]> {
      return requestJson(`${root}/suggestions/reject`, {
        method: "POST",
        headers: roleHeaders(true),
        body: JSON.stringify({ suggestion_ids: suggestionIds, reason }),
      }).then((payload) => {
        if (!isRecord(payload) || !Array.isArray(payload.rejected)) {
          throw new ApiError(200, "validation_error", "The API omitted rejected suggestions.");
        }
        return payload.rejected.map(parseSuggestion);
      });
    },
  };
}

export type VisitClient = ReturnType<typeof createClient>;
