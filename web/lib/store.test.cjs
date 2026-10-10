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
  useStore.setState({ actions: [action], approvingIds: [], approvalErrors: {}, patients: { patient: { id: "patient" } }, conversations: [conversation], audit: [], notice: null });
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
