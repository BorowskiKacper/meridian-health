export type Citation = {
  source_id: string;
  title: string;
  passage: string;
  locator: string;
  tier: string;
};

export type Suggestion = {
  id: string;
  patient_id: string;
  request_id: string | null;
  kind: string;
  status: string;
  target_table: string;
  target_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string;
  confidence: number | null;
  citations: Citation[];
  validation_flags: string[];
  source: string;
};

export type Answer = {
  text: string;
  citations: Citation[];
};

export type DoctorRequest = {
  request_id: string;
  transcript: string;
  route: string;
  suggestions: Suggestion[];
  answer: Answer | null;
  spoken_text: string | null;
  audio_base64: string | null;
};

export type ReminderReview = {
  suggestions: Suggestion[];
  answer: string | null;
};

export type ApproveResult = {
  approved: Suggestion[];
  reminder_review: ReminderReview;
};
