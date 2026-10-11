import assert from "node:assert/strict";
import { test } from "node:test";

import {
  STARTERS,
  actionDetail,
  chatRoute,
  chatRouteLabel,
  confidenceText,
  formatPatch,
  patientMrn,
  phoneReply,
  replyText,
  WEB_HANDOFF,
} from "./chat";

test("mrn matches the web chart prefix", () => {
  assert.equal(patientMrn("11111111-1111-4111-8111-111111111111"), "R-111111");
  assert.equal(patientMrn("22222222-2222-4222-8222-222222222222"), "R-222222");
});

test("assistant routes use the web chat labels", () => {
  assert.equal(chatRouteLabel(chatRoute("chart_update")!), "Chart");
  assert.equal(chatRouteLabel(chatRoute("clinical_question")!), "Ask");
  assert.equal(chatRouteLabel(chatRoute("check_screenings")!), "Screening");
  assert.equal(chatRoute("navigate"), null);
});

test("reply text matches the web assistant", () => {
  assert.equal(
    replyText({ answer: { text: "LDL is high.", citations: [] }, suggestions: [] }),
    "LDL is high.",
  );
  assert.equal(
    replyText({ answer: null, suggestions: [suggestion()] }),
    "Drafted 1 chart change. Nothing is written until you approve.",
  );
  assert.equal(
    replyText({ answer: null, suggestions: [suggestion(), suggestion()] }),
    "Drafted 2 chart changes. Nothing is written until you approve.",
  );
  assert.equal(replyText({ answer: null, suggestions: [] }), "Nothing new was proposed.");
});

test("action cards format patches the way the web chat does", () => {
  assert.equal(formatPatch({ status: "active", name: "Hypertension" }), "status: active, name: Hypertension");
  assert.equal(formatPatch({}), undefined);
  assert.equal(formatPatch(null), undefined);
  assert.equal(actionDetail(suggestion()), "field update · conditions");
  assert.equal(confidenceText(0.91), "91%");
  assert.equal(confidenceText(null), undefined);
});

test("starters are questions, and chart work points to the web app", () => {
  assert.deepEqual([...STARTERS], ["Are screenings up to date?", "What does the guideline recommend?"]);
  const answer = phoneReply({
    route: "clinical_question",
    answer: { text: "LDL is high.", citations: [] },
    suggestions: [],
  });
  assert.equal(answer.text, "LDL is high.");
  assert.equal(answer.answer?.text, "LDL is high.");
  const chart = phoneReply({
    route: "chart_update",
    answer: null,
    suggestions: [suggestion()],
  });
  assert.equal(chart.text, WEB_HANDOFF);
  assert.equal(chart.answer, null);
});

function suggestion() {
  return {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    patient_id: "11111111-1111-4111-8111-111111111111",
    request_id: null,
    kind: "field_update",
    status: "pending",
    target_table: "conditions",
    target_id: null,
    before: { status: "active" },
    after: { status: "controlled" },
    reason: "Mark hypertension controlled.",
    confidence: 0.91,
    citations: [],
    validation_flags: [],
    source: "chart",
  };
}
