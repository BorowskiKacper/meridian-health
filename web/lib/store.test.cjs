const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const ts = require("typescript");

// Exercise the real store with controllable API responses, without a browser.
require.extensions[".ts"] = (module, filename) => {
  const source = fs.readFileSync(filename, "utf8");
  module._compile(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
};
const api = require("./api.ts");
const chart = require("./chart.ts");
const { useStore } = require("./store.ts");

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup() {
  const action = { id: "proposal", patientId: "patient", status: "pending", title: "Visit note", conversationId: "conversation", messageId: "message" };
  const conversation = { id: "conversation", patientId: "patient", messages: [{ id: "message", role: "agent", text: "Review this note." }] };
  useStore.setState({ actions: [action], approvingIds: [], approvalErrors: {}, routePreviews: {}, patients: { patient: { id: "patient" } }, conversations: [conversation], audit: [], notice: null });
  return { action, conversation };
}

test("approval acknowledges immediately, ignores duplicate clicks and stays quiet", async () => {
  const { action, conversation } = setup();
  const request = deferred();
  const refresh = deferred();
  let calls = 0;
  api.approveSuggestions = () => { calls++; return request.promise; };
  chart.reloadPatient = () => refresh.promise;
  const approval = useStore.getState().approveSelected([action.id]);
  assert.deepEqual(useStore.getState().approvingIds, [action.id]);
  assert.equal(useStore.getState().actions[0].status, "pending");
  assert.equal(await useStore.getState().approveSelected([action.id]), false);
  assert.equal(calls, 1);
  request.resolve({ approved: [{ id: action.id }], reminder_review: { answer: "Unrequested screening output", suggestions: [] } });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(useStore.getState().actions[0].status, "approved");
  assert.deepEqual(useStore.getState().conversations, [conversation]);
  refresh.resolve({ patient: { id: "patient" }, actions: [{ ...action, status: "approved" }] });
  assert.equal(await approval, true);
  assert.deepEqual(useStore.getState().approvingIds, []);
});

test("failed approval clears the busy state and leaves the proposal pending", async () => {
  const { action } = setup();
  const request = deferred();
  api.approveSuggestions = () => request.promise;
  const approval = useStore.getState().approveSelected([action.id]);
  request.reject(new api.ApiError("Approval unavailable", 503));
  assert.equal(await approval, false);
  assert.deepEqual(useStore.getState().approvingIds, []);
  assert.equal(useStore.getState().actions[0].status, "pending");
  assert.equal(useStore.getState().notice, "Approval unavailable");
  assert.equal(useStore.getState().approvalErrors[action.id], "Approval unavailable");
  api.approveSuggestions = async () => ({ approved: [{ id: action.id }] });
  chart.reloadPatient = async () => ({ patient: { id: "patient" }, actions: [{ ...action, status: "approved" }] });
  assert.equal(await useStore.getState().approveSelected([action.id]), true);
  assert.equal(useStore.getState().approvalErrors[action.id], undefined);
});

test("a refresh failure preserves the confirmed approval", async () => {
  const { action } = setup();
  api.approveSuggestions = async () => ({ approved: [{ id: action.id }] });
  chart.reloadPatient = async () => { throw new Error("Refresh unavailable"); };
  assert.equal(await useStore.getState().approveSelected([action.id]), true);
  assert.equal(useStore.getState().actions[0].status, "approved");
  assert.deepEqual(useStore.getState().approvingIds, []);
  assert.match(useStore.getState().notice, /approved, but the chart could not refresh/);
});

test("workflow selection is isolated and research preserves evidence metadata", async () => {
  const { conversation } = setup();
  useStore.setState({ activeConversationId: conversation.id, requestModes: {}, actions: [] });
  useStore.getState().setRequestMode(conversation.id, "clinical_question");
  assert.equal(useStore.getState().requestModes.other, undefined);
  const request = deferred();
  let sent;
  api.postRequest = (...args) => { sent = args; return request.promise; };
  chart.reloadPatient = async () => ({ patient: { id: "patient" }, actions: [] });
  useStore.getState().sendConfirmed("Open the timeline");
  assert.deepEqual(sent, ["patient", "Open the timeline", "clinical_question"]);
  assert.equal(useStore.getState().conversations[0].messages.at(-1).pending, true);
  const citation = { source_id: "study", title: "Study", locator: "https://pubmed.ncbi.nlm.nih.gov/123/", tier: "literature", passage: "Evidence." };
  request.resolve({ route: "clinical_question", transcript: "Open the timeline", suggestions: [], answer: { text: "Answer.", citations: [citation], sections: [{ title: "Clinical interpretation", text: "Answer.", source_ids: ["study"] }] } });
  await new Promise((resolve) => setImmediate(resolve));
  const message = useStore.getState().conversations[0].messages.at(-1);
  assert.equal(message.pending, false);
  const research = useStore.getState().research[message.researchId];
  assert.equal(research.citations[0].locator, citation.locator);
  assert.equal(research.citations[0].id, "study");
  assert.equal(research.sections[0].text, "Answer.");
});

test("screening answers do not create duplicate research cards and failures stay inline", async () => {
  const { conversation } = setup();
  useStore.setState({ activeConversationId: conversation.id, requestModes: {} });
  api.postRequest = async () => ({ route: "check_screenings", suggestions: [], answer: { text: "Screening status.", citations: [] } });
  chart.reloadPatient = async () => ({ patient: { id: "patient" }, actions: [] });
  useStore.getState().sendConfirmed("Review screenings");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(useStore.getState().conversations[0].messages.at(-1).researchId, undefined);
  api.postRequest = async () => { throw new api.ApiError("Research unavailable", 503); };
  useStore.getState().sendConfirmed("Clinical question");
  await new Promise((resolve) => setImmediate(resolve));
  const message = useStore.getState().conversations[0].messages.at(-1);
  assert.equal(message.error, true);
  assert.equal(message.text, "Research unavailable");
});

test("research rendering supports safe links, chart excerpts and legacy answers", () => {
  const Module = require("node:module");
  const path = require("node:path");
  const original = Module._resolveFilename;
  Module._resolveFilename = function (specifier, ...args) {
    return original.call(this, specifier.startsWith("@/") ? path.resolve(specifier.slice(2)) : specifier, ...args);
  };
  require.extensions[".tsx"] = (module, filename) => {
    module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText, filename);
  };
  try {
    const React = require("react");
    const { renderToStaticMarkup } = require("react-dom/server");
    const { ResearchResult } = require("../components/agent/research-result.tsx");
    const result = { id: "research", patientId: "patient", answer: "Duplicate fallback answer", citations: [{ id: "study", source: "Study", tier: "literature", passage: "Evidence", locator: "https://pubmed.ncbi.nlm.nih.gov/123/" }, { id: "bad", source: "Unsafe source", tier: "literature", passage: "Excerpt", locator: "javascript:alert(1)" }, { id: "chart", source: "Recorded weight", tier: "chart", passage: JSON.stringify({ name: "Weight", value: 68, unit: "kg", patient_id: "hidden-patient-id" }), locator: "observation:chart" }], sections: [{ title: "Clinical interpretation", text: "One clinical answer", source_ids: ["study"] }] };
    const html = renderToStaticMarkup(React.createElement(ResearchResult, { result, compact: true }));
    assert.match(html, /One clinical answer/);
    assert.doesNotMatch(html, /Duplicate fallback answer|javascript:|hidden-patient-id/);
    assert.match(html, /Findings used/);
    assert.match(html, /View in chart/);
    assert.match(html, /href="https:\/\/pubmed/);
    const legacy = renderToStaticMarkup(React.createElement(ResearchResult, { result: { ...result, sections: undefined } }));
    assert.match(legacy, /Duplicate fallback answer/);
    const { Composer } = require("../components/agent/composer.tsx");
    setup();
    const composerSizes = [undefined, "clinical_question", "chart_update", "check_screenings"].map((mode) => {
      useStore.getState().setRequestMode("conversation", mode);
      const markup = renderToStaticMarkup(React.createElement(Composer, { conversationId: "conversation" }));
      assert.doesNotMatch(markup, /Draft.*Review.*Approve/);
      assert.match(markup, /Research/);
      assert.match(markup, /rows="2"/);
      return markup.match(/<textarea[^>]*class="([^"]*)"/)[1];
    });
    assert.equal(new Set(composerSizes).size, 1);
    assert.match(composerSizes[0], /h-20/);
  } finally { Module._resolveFilename = original; }
});

test("a weight change in Research asks to switch before submitting", async () => {
  const { conversation } = setup();
  useStore.setState({ activeConversationId: conversation.id, requestModes: { conversation: "clinical_question" } });
  const preview = deferred();
  api.previewRequest = () => preview.promise;
  const submissions = [];
  api.postRequest = async (...args) => { submissions.push(args); return { route: "chart_update", suggestions: [], answer: null }; };
  chart.reloadPatient = async () => ({ patient: { id: "patient" }, actions: [] });
  useStore.getState().send("Change weight to 70 kg");
  assert.equal(useStore.getState().routePreviews.conversation.status, "checking");
  assert.equal(submissions.length, 0);
  preview.resolve({ route: "chart_update", transcript: "Change weight to 70 kg", description: "Draft chart changes." });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(useStore.getState().routePreviews.conversation.status, "ready");
  assert.equal(submissions.length, 0);
  assert.equal(useStore.getState().conversations[0].messages.length, 1);
  useStore.getState().confirmRoutePreview(conversation.id);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(submissions, [["patient", "Change weight to 70 kg", "chart_update"]]);
  assert.equal(useStore.getState().requestModes.conversation, "chart_update");
});

test("Auto waits for confirmation and cancelled previews cannot submit late", async () => {
  const { conversation } = setup();
  useStore.setState({ activeConversationId: conversation.id, requestModes: {} });
  let submissions = 0;
  api.postRequest = async () => { submissions++; return { route: "clinical_question", suggestions: [], answer: null }; };
  api.previewRequest = async () => ({ route: "clinical_question", transcript: "Clinical question", description: "Research evidence." });
  useStore.getState().send("Clinical question");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(submissions, 0);
  useStore.getState().cancelRoutePreview(conversation.id);
  useStore.getState().confirmRoutePreview(conversation.id);
  assert.equal(submissions, 0);
  const preview = deferred();
  api.previewRequest = () => preview.promise;
  useStore.getState().send("Clinical question");
  useStore.getState().cancelRoutePreview(conversation.id);
  preview.resolve({ route: "clinical_question", transcript: "Clinical question", description: "Research evidence." });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(useStore.getState().routePreviews.conversation, undefined);
  assert.equal(submissions, 0);
});

test("General chat is always available and never attaches the open patient", async () => {
  chart.loadWorkspace = async () => ({ patients: [], actions: [] });
  api.getCapabilities = async () => ({ assistant: true });
  await useStore.getState().load();
  assert.equal(useStore.getState().activeConversationId, "general");
  assert.equal(useStore.getState().conversations[0].patientId, null);
  useStore.setState({ patients: { amy: { id: "amy", name: "Amy Lee" } }, activeTabId: "amy-chart", tabs: [{ id: "amy-chart", patientId: "amy" }] });
  let submitted;
  api.postGeneralChat = async (...args) => { submitted = args; return { route: "clinical_question", transcript: "General question", answer: { text: "General evidence", citations: [] }, suggestions: [{ id: "should-not-be-added" }] }; };
  chart.reloadPatient = () => { throw new Error("General chat must not refresh a patient"); };
  api.previewRequest = () => { throw new Error("General chat must not preview against a patient"); };
  useStore.getState().send("General question");
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(submitted, ["General question", undefined]);
  const reply = useStore.getState().conversations[0].messages.at(-1);
  assert.equal(reply.error, undefined);
  assert.equal(useStore.getState().research[reply.researchId].patientId, null);
  assert.equal(useStore.getState().actions.length, 0);
});

test("add to plan posts the API citations, queues a pending research suggestion, and keeps failures retryable", async () => {
  setup();
  const citation = { source_id: "study", title: "Study", passage: "Evidence.", locator: "https://pubmed.ncbi.nlm.nih.gov/123/", tier: "literature" };
  const research = { id: "r1", patientId: "patient", question: "Q", answer: "  Start an SGLT2 inhibitor.  ", basis: "", citations: [{ source: "Study", passage: "Evidence.", id: "study", tier: "literature" }], requestId: "req-1", apiCitations: [citation] };
  useStore.setState({ actions: [], research: { r1: research } });
  api.createPlanItem = async () => { throw new api.ApiError("Plan unavailable", 400); };
  await useStore.getState().addToPlan("r1");
  assert.equal(useStore.getState().research.r1.plan.status, "error");
  assert.equal(useStore.getState().research.r1.plan.message, "Plan unavailable");
  assert.equal(useStore.getState().actions.length, 0);
  let sent;
  api.createPlanItem = async (...args) => { sent = args; return { id: "s1", patient_id: "patient", kind: "plan_item", status: "pending", target_table: "notes", before: {}, after: { body: args[2] }, reason: args[2], confidence: 1, citations: args[3], source: "research_add_to_plan" }; };
  let refreshedWith;
  // The server's pending list includes the new suggestion, so refresh keeps it queued.
  chart.reloadPatient = async () => { refreshedWith = useStore.getState().actions; return { patient: { id: "patient" }, actions: refreshedWith }; };
  await useStore.getState().addToPlan("r1");
  assert.ok(refreshedWith.some((a) => a.id === "s1"));
  assert.deepEqual(sent, ["patient", "req-1", "Start an SGLT2 inhibitor.", [citation]]);
  const action = useStore.getState().actions.find((a) => a.id === "s1");
  assert.equal(action.status, "pending");
  assert.equal(action.agent, "research");
  assert.equal(useStore.getState().research.r1.plan.status, "added");
  await useStore.getState().addToPlan("r1");
  assert.equal(useStore.getState().actions.filter((a) => a.id === "s1").length, 1);
});

test("general questions and empty answers never offer add to plan", async () => {
  setup();
  let calls = 0;
  api.createPlanItem = async () => { calls++; };
  useStore.setState({ research: { g: { id: "g", patientId: null, question: "Q", answer: "General answer", basis: "", citations: [] }, e: { id: "e", patientId: "patient", question: "Q", answer: "  ", basis: "", citations: [] } } });
  await useStore.getState().addToPlan("g");
  await useStore.getState().addToPlan("e");
  assert.equal(calls, 0);
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const { ResearchResult } = require("../components/agent/research-result.tsx");
  assert.doesNotMatch(renderToStaticMarkup(React.createElement(ResearchResult, { result: useStore.getState().research.g })), /Add to plan/);
  assert.match(renderToStaticMarkup(React.createElement(ResearchResult, { result: { ...useStore.getState().research.g, patientId: "patient" } })), /Add to plan/);
});
