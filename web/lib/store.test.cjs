const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const ts = require("typescript");

// Exercise the real store with controllable API responses, without a browser.
require.extensions[".ts"] = (module, filename) => {
  const source = fs.readFileSync(filename, "utf8");
  module._compile(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
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

test("closing patient chats preserves General and clears only the closed chat's routing state", () => {
  const general = { id: "general", patientId: null, title: "General", messages: [] };
  const first = { id: "first", patientId: "patient", messages: [] };
  const second = { id: "second", patientId: "other", messages: [] };
  useStore.setState({
    conversations: [general, first, second], activeConversationId: "first",
    requestModes: { first: "chart_update", second: "clinical_question" },
    routePreviews: { first: { status: "ready", text: "Change weight", route: "chart_update" } },
  });
  useStore.getState().closeConversation("second");
  assert.equal(useStore.getState().activeConversationId, "first");
  assert.equal(useStore.getState().requestModes.first, "chart_update");
  useStore.getState().closeConversation("first");
  assert.equal(useStore.getState().activeConversationId, "general");
  assert.deepEqual(useStore.getState().conversations, [general]);
  assert.deepEqual(useStore.getState().requestModes, {});
  assert.deepEqual(useStore.getState().routePreviews, {});
  useStore.getState().closeConversation("general");
  assert.deepEqual(useStore.getState().conversations, [general]);
});

test("workspace result replay preserves evidence and never duplicates messages", async () => {
  useStore.setState({ conversations: [{ id: 'general', patientId: null, title: 'General', messages: [] }], workspaceJobs: {}, research: {}, actions: [] });
  const job = { id: 'shared-result', status: 'completed', text: 'General research', patient_id: null, patient_name: null, desktop_applied: false, response: { route: 'clinical_question', suggestions: [], answer: { text: 'Evidence answer', citations: [{ title: 'Study', source_id: 'source', locator: 'https://pubmed.ncbi.nlm.nih.gov/1/', passage: 'Evidence passage', tier: 'literature' }] } } };
  await useStore.getState().syncWorkspaceJob(job);
  await useStore.getState().syncWorkspaceJob(job);
  await useStore.getState().syncWorkspaceJob({ ...job, desktop_applied: true });
  assert.equal(useStore.getState().conversations[0].messages.length, 2);
  assert.equal(useStore.getState().research[job.id].citations[0].passage, 'Evidence passage');
  assert.equal(useStore.getState().research[job.id].patientId, null);
});

test("a workspace clarification moves into view without choosing an ambiguous patient", async () => {
  useStore.setState({ conversations: [{ id: 'general', patientId: null, title: 'General', messages: [] }], activeConversationId: 'other', workspaceJobs: {}, layout: 'workspace' });
  const job = { id: 'clarify', status: 'needs_patient', text: 'Open Amy trends', patient_id: null, patient_name: null, desktop_applied: false, question: 'Which patient?', candidates: [{ id: 'amy', display_name: 'Amy', date_of_birth: '1990-01-01' }] };
  await useStore.getState().syncWorkspaceJob(job);
  assert.equal(useStore.getState().activeConversationId, 'general');
  assert.equal(useStore.getState().layout, 'split');
  assert.equal(useStore.getState().conversations[0].patientId, null);
  assert.equal(useStore.getState().conversations[0].messages.at(-1).text, 'Which patient?');
});

test("queued mobile prompts do not wait for loading a new patient's chart", async (t) => {
  const original = chart.reloadPatient;
  t.after(() => { chart.reloadPatient = original; });
  let calls = 0;
  chart.reloadPatient = async () => { calls++; return { patient: { id: 'new-patient', name: 'Amy Lee' }, actions: [] }; };
  useStore.setState({ patients: {}, conversations: [{ id: 'general', patientId: null, title: 'General', messages: [] }], activeConversationId: 'general', workspaceJobs: {} });
  const job = { id: 'quick-command', status: 'queued', text: 'Open Amy Lee vitals', patient_id: 'new-patient', patient_name: 'Amy Lee', desktop_applied: false };
  await useStore.getState().syncWorkspaceJob(job);
  assert.equal(calls, 0);
  assert.equal(useStore.getState().conversations[0].messages[0].text, job.text);
  await useStore.getState().syncWorkspaceJob({ ...job, status: 'completed', response: { route: 'navigate', suggestions: [] } });
  assert.equal(calls, 1);
  assert.equal(useStore.getState().conversations.find((c) => c.patientId === 'new-patient').messages.length, 2);
});

test("paired desktop preserves workflow confirmation before durable submission", async (t) => {
  const workspace = require('./workspace-api.ts');
  const original = workspace.submitWorkspace;
  workspace.setWorkspaceToken('test-device');
  t.after(() => { workspace.setWorkspaceToken(null); workspace.submitWorkspace = original; });
  const { conversation } = setup();
  useStore.setState({ activeConversationId: conversation.id, requestModes: { conversation: 'clinical_question' }, workspaceJobs: {} });
  api.previewRequest = async () => ({ route: 'chart_update', transcript: 'Change weight to 70 kg', description: 'Draft chart changes.' });
  const submissions = [];
  workspace.submitWorkspace = async (text, audio, patientId, route, id) => {
    submissions.push({ text, patientId, route });
    return { id, text, status: 'queued', patient_id: patientId, patient_name: null, desktop_applied: false };
  };
  useStore.getState().send('Change weight to 70 kg');
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(useStore.getState().routePreviews.conversation.status, 'ready');
  assert.equal(submissions.length, 0);
  useStore.getState().confirmRoutePreview(conversation.id);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(submissions, [{ text: 'Change weight to 70 kg', patientId: 'patient', route: 'chart_update' }]);
  assert.equal(Object.values(useStore.getState().workspaceJobs)[0].status, 'queued');
});

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
    module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX } }).outputText, filename);
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

test("chat navigation switches chart sections and patients without classifying", async () => {
  const amy = { id: "amy", name: "Amy Lee" }, john = { id: "john", name: "John Roe" };
  const conversations = () => [{ id: "conv-amy", patientId: "amy", messages: [] }, { id: "conv-john", patientId: "john", messages: [] }];
  useStore.setState({ patients: { amy, john }, conversations: conversations(), activeConversationId: "conv-amy", tabs: [{ id: "amy-lab", kind: "lab", patientId: "amy" }], activeTabId: null, requestModes: {}, routePreviews: {}, layout: "agent" });
  let classified = 0;
  api.previewRequest = async () => { classified++; return { route: "chart_update", transcript: "Open labs and draft a note", description: "Draft." }; };
  const messages = (id) => useStore.getState().conversations.find((c) => c.id === id).messages;
  useStore.getState().send("Switch to the labs tab");
  assert.equal(useStore.getState().activeTabId, "amy-lab", "an open tab is reused");
  assert.equal(useStore.getState().layout, "split");
  for (const [text, kind] of [["go to medications", "medications"], ["show blood pressure", "vitals"]]) {
    useStore.getState().send(text);
    assert.equal(useStore.getState().tabs.find((t) => t.id === useStore.getState().activeTabId).kind, kind);
  }
  assert.equal(messages("conv-amy").at(-1).text, "Opened it beside the chart.");
  useStore.getState().send("I want to see John Roe's information");
  const active = useStore.getState().tabs.find((t) => t.id === useStore.getState().activeTabId);
  assert.deepEqual([active.kind, active.patientId, useStore.getState().activeConversationId], ["overview", "john", "conv-john"]);
  assert.equal(messages("conv-john").at(-1).text, "Opened John Roe's chart.");
  useStore.setState({ activeConversationId: "conv-amy" });
  const before = useStore.getState().activeTabId;
  useStore.getState().send("Show Jim Smith's chart");
  assert.equal(useStore.getState().activeTabId, before);
  assert.equal(useStore.getState().activeConversationId, "conv-amy");
  assert.match(messages("conv-amy").at(-1).text, /couldn't identify/);
  assert.equal(classified, 0);
  useStore.setState({ requestModes: { "conv-amy": "clinical_question" } });
  useStore.getState().send("go to medications");
  useStore.getState().cancelRoutePreview("conv-amy");
  useStore.setState({ requestModes: {} });
  useStore.getState().send("Open labs and draft a note");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(classified, 2, "a chosen workflow and mixed requests still classify");
  assert.equal(useStore.getState().routePreviews["conv-amy"].status, "ready");
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

test("vitals list always shows expected rows, as Not recorded when missing", (t) => {
  const Module = require("node:module");
  const path = require("node:path");
  const original = Module._resolveFilename;
  Module._resolveFilename = function (specifier, ...args) {
    return original.call(this, specifier.startsWith("@/") ? path.resolve(specifier.slice(2)) : specifier, ...args);
  };
  t.after(() => { Module._resolveFilename = original; });
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const { MeasurementList } = require("../components/charts/measurement-list.tsx");
  const series = [{ name: "Heart rate", unit: "beats/min", points: [{ at: "2025-01-01T00:00:00Z", value: 70 }, { at: "2025-06-01T00:00:00Z", value: 76 }] }];
  const html = renderToStaticMarkup(React.createElement(MeasurementList, { series, showChange: true, expected: [{ name: "Heart rate", match: /^heart rate$/i }, { name: "Respiratory rate", match: /^respiratory rate$/i }] }));
  assert.match(html, /Respiratory rate.*Not recorded/);
  assert.doesNotMatch(html, /Heart rate<\/span><span[^>]*>Not recorded/);
  assert.match(html, /\+6/);
});
const { demoPrompts, demoPrompt } = require('./demo-prompts.ts');

test('demo chips follow patient and mode, with two General chips and none for Auto', () => {
  assert.equal(demoPrompts(null).length, 2);
  assert.ok(!demoPrompts(null).some((p) => p.label === 'Clinical documentation'));
  for (const digit of ['1', '2', '3']) {
    const patientId = `${digit.repeat(8)}-${digit.repeat(4)}-4${digit.repeat(3)}-8${digit.repeat(3)}-${digit.repeat(12)}`;
    assert.deepEqual(demoPrompts(patientId), []);
    for (const route of ['clinical_question', 'check_screenings', 'chart_update']) {
      const prompts = demoPrompts(patientId, route);
      assert.equal(prompts.length, 1);
      assert.equal(demoPrompt(patientId, prompts[0].text), prompts[0]);
      assert.equal(demoPrompt(null, prompts[0].text), undefined);
    }
  }
  assert.deepEqual(demoPrompts('unknown', 'clinical_question'), []);
  assert.deepEqual(demoPrompts(undefined), []);
});

test('a scripted patient sentence submits without a routing preview', () => {
  const prompt = demoPrompts('22222222-2222-4222-8222-222222222222', 'clinical_question')[0];
  const original = useStore.getState().sendConfirmed;
  const calls = [];
  useStore.setState({ conversations: [{ id: 'demo', patientId: prompt.patient_id, messages: [] }], activeConversationId: 'demo', routePreviews: {}, sendConfirmed: (...args) => calls.push(args) });
  try {
    useStore.getState().send(prompt.text);
    assert.deepEqual(calls, [[prompt.text, undefined, prompt.route, 'demo']]);
    assert.deepEqual(useStore.getState().routePreviews, {});
  } finally { useStore.setState({ sendConfirmed: original }); }
});

test('composer renders one selected patient chip, none for Auto, and both General chips, never a checking status', () => {
  const Module = require('node:module');
  const path = require('node:path');
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const storeModule = require('./store.ts');
  const originalStore = storeModule.useStore;
  const originalResolve = Module._resolveFilename;
  Module._resolveFilename = function (specifier, ...args) {
    return originalResolve.call(this, specifier.startsWith('@/') ? path.resolve(__dirname, '..', specifier.slice(2)) : specifier, ...args);
  };
  require.extensions['.tsx'] = (module, filename) => {
    module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX } }).outputText, filename);
  };
  try {
    const { Composer } = require('../components/agent/composer.tsx');
    const render = (patientId, mode, preview) => {
      const state = { ...originalStore.getState(), conversations: [{ id: 'demo', patientId, messages: [] }], routePreviews: preview ? { demo: preview } : {}, requestModes: { demo: mode } };
      storeModule.useStore = (selector) => selector(state);
      return renderToStaticMarkup(React.createElement(Composer, { conversationId: 'demo' }));
    };
    const patient = '22222222-2222-4222-8222-222222222222';
    assert.doesNotMatch(render(patient), /aria-label="Demo prompts"/);
    assert.doesNotMatch(render('unknown', 'clinical_question'), /aria-label="Demo prompts"/);
    for (const route of ['clinical_question', 'check_screenings', 'chart_update']) {
      const html = render(patient, route);
      assert.equal((html.match(/<button[^>]* title=/g) || []).length, 1);
      assert.match(html, new RegExp(demoPrompts(patient, route)[0].label));
    }
    const general = render(null);
    assert.equal((general.match(/<button[^>]* title=/g) || []).length, 2);
    assert.doesNotMatch(render(patient, undefined, { status: 'checking', text: 'Clinical question' }), /Checking which workflow/);
    assert.doesNotMatch(general, /aria-label="Request workflow"/);
  } finally {
    storeModule.useStore = originalStore;
    Module._resolveFilename = originalResolve;
  }
});

test("approved Document rows open the chart tab that shows each written change", async () => {
  const row = (id, patient_id, target_table, after, source = "chart_agent") => ({ id, patient_id, target_table, after, before: {}, source });
  const approve = async (patientId, rows, tabs = []) => {
    const actions = rows.map((r) => ({ id: r.id, patientId, status: "pending", title: r.target_table }));
    useStore.setState({ actions, approvingIds: [], tabs, activeTabId: null, layout: "agent", chartHistory: {}, patients: { [patientId]: { id: patientId } } });
    api.approveSuggestions = async () => ({ approved: rows });
    chart.reloadPatient = async () => ({ patient: { id: patientId }, actions: actions.map((a) => ({ ...a, status: "approved" })) });
    assert.equal(await useStore.getState().approveSelected(actions.map((a) => a.id)), true);
    const s = useStore.getState();
    return { kinds: s.tabs.map((t) => `${t.kind}${t.refId ? `:${t.refId}` : ""}`), active: s.tabs.find((t) => t.id === s.activeTabId), s };
  };

  // Jane / John: a discussion note lands on the notes timeline, not the Visit draft.
  for (const patient of ["jane", "john"]) {
    const { kinds, active, s } = await approve(patient, [row("n", patient, "notes", { body: "Discussed." })]);
    assert.deepEqual(kinds, ["timeline:notes"]);
    assert.equal(active.patientId, patient);
    assert.equal(s.layout, "split");
  }

  // Amy: stopped iron is focused with history on; hemoglobin/ferritin open Diagnostics; reminder rows are ignored.
  const amy = await approve("amy", [
    row("m", "amy", "medications", { status: "stopped" }),
    row("h", "amy", "observations", { name: "Hemoglobin", value: 13, unit: "g/dL" }),
    row("f", "amy", "observations", { name: "Ferritin", value: 46, unit: "ng/mL" }),
    row("r", "amy", "reminder_schedule", { status: "scheduled" }, "reminder_agent"),
  ]);
  assert.deepEqual(amy.kinds, ["lab", "medications"]);
  assert.equal(amy.active.kind, "medications");
  assert.equal(amy.s.chartHistory["amy:medications"], true);

  // An already-open problems tab is reused and its history checkbox turned on; vitals map by name.
  const open = await approve("p", [row("c", "p", "conditions", { status: "resolved" }), row("w", "p", "observations", { name: "Body weight" })], [{ id: "existing", kind: "problems", patientId: "p" }]);
  assert.deepEqual(open.kinds, ["problems", "vitals"]);
  assert.equal(open.active.id, "existing");
  assert.equal(open.s.chartHistory["p:problems"], true);

  // Unmapped or non-Document rows open nothing.
  assert.deepEqual((await approve("q", [row("x", "q", "encounters", {}), row("y", "q", "notes", {}, "research_add_to_plan")])).kinds, []);
});
