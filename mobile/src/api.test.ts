import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";

import {
  ApiError,
  buildDoctorRequest,
  createClient,
  filenameForMime,
  parseDoctorRequest,
} from "./api";

const JANE = "11111111-1111-4111-8111-111111111111";
const REQUEST = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("buildDoctorRequest", () => {
  test("typed input sends text and leaves audio off the form", () => {
    const form = buildDoctorRequest(JANE, { text: "  Mark hypertension controlled.  " });
    assert.deepEqual([...form.keys()].sort(), ["patient_id", "text"]);
    assert.equal(form.get("patient_id"), JANE);
    assert.equal(form.get("text"), "Mark hypertension controlled.");
    assert.equal(form.get("audio"), null);
  });

  test("dictation sends audio and leaves text off the form", () => {
    const blob = new Blob([Uint8Array.from([1, 2, 3])], { type: "audio/webm" });
    const form = buildDoctorRequest(JANE, { audio: blob });
    assert.deepEqual([...form.keys()].sort(), ["audio", "patient_id"]);
    assert.equal(form.get("text"), null);
    const audio = form.get("audio");
    assert.ok(audio instanceof File);
    assert.equal(audio.name, "dictation.webm");
    assert.equal(audio.type, "audio/webm");
  });

  test("a native recording is one audio part", () => {
    const form = buildDoctorRequest(JANE, {
      audio: { uri: "file:///cache/dictation.m4a", name: "dictation.m4a", type: "audio/mp4" },
    });
    assert.deepEqual([...form.keys()].sort(), ["audio", "patient_id"]);
    assert.equal(form.get("text"), null);
  });

  test("blank text is refused before a request is built", () => {
    assert.throws(() => buildDoctorRequest(JANE, { text: "   " }), ApiError);
  });
});

test("filename follows the recording mime type", () => {
  assert.equal(filenameForMime("audio/webm"), "dictation.webm");
  assert.equal(filenameForMime("audio/mp4"), "dictation.m4a");
  assert.equal(filenameForMime("audio/wav"), "dictation.wav");
});

test("parseDoctorRequest accepts the contract body", () => {
  const parsed = parseDoctorRequest({
    request_id: REQUEST,
    transcript: "Mark hypertension controlled.",
    route: "chart_update",
    suggestions: [],
    answer: null,
    spoken_text: null,
    audio_base64: null,
  });
  assert.equal(parsed.route, "chart_update");
  assert.equal(parsed.answer, null);
  assert.deepEqual(parsed.suggestions, []);
});

describe("createClient", () => {
  test("posts one typed request with the doctor role and no content type", async () => {
    let seen: { url: string; method: string; role: string | null; contentType: string | null; keys: string[] } | null =
      null;
    globalThis.fetch = async (input, init) => {
      const headers = new Headers(init?.headers);
      const body = init?.body as FormData;
      seen = {
        url: String(input),
        method: init?.method ?? "GET",
        role: headers.get("X-Role"),
        contentType: headers.get("Content-Type"),
        keys: [...body.keys()],
      };
      return new Response(
        JSON.stringify({
          request_id: REQUEST,
          transcript: "What is her LDL?",
          route: "clinical_question",
          suggestions: [],
          answer: {
            text: "LDL is above the range discussed in the cited guideline.",
            citations: [
              {
                source_id: "uspstf:example",
                title: "USPSTF",
                passage: "Screen.",
                locator: "https://www.uspreventiveservicestaskforce.org/example",
                tier: "baseline",
              },
            ],
          },
          spoken_text: null,
          audio_base64: null,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    const result = await createClient("http://api.test").sendRequest(JANE, { text: "What is her LDL?" });
    assert.equal(seen?.url, "http://api.test/requests");
    assert.equal(seen?.method, "POST");
    assert.equal(seen?.role, "doctor");
    assert.equal(seen?.contentType, null);
    assert.deepEqual(seen?.keys.sort(), ["patient_id", "text"]);
    assert.equal(result.answer?.text, "LDL is above the range discussed in the cited guideline.");
    assert.equal(result.answer?.citations[0]?.tier, "baseline");
  });

  test("surfaces the contract error body", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({ error: { code: "validation_error", message: "Audio could not be transcribed." } }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    await assert.rejects(
      () => createClient("http://api.test").sendRequest(JANE, { audio: new Blob(["x"], { type: "audio/webm" }) }),
      (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.code, "validation_error");
        assert.equal(error.message, "Audio could not be transcribed.");
        assert.equal(error.status, 400);
        return true;
      },
    );
  });

  test("approve, reject, add to plan, and the queue use the contract paths", async () => {
    const calls: { url: string; method: string; json: unknown }[] = [];
    globalThis.fetch = async (input, init) => {
      const url = String(input);
      let json: unknown = null;
      if (typeof init?.body === "string") json = JSON.parse(init.body);
      calls.push({ url, method: init?.method ?? "GET", json });
      if (url.includes("/suggestions/approve")) {
        return Response.json({
          approved: [{ id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", status: "approved" }],
          reminder_review: { suggestions: [], answer: "Screenings are up to date." },
        });
      }
      if (url.includes("/suggestions/reject")) {
        return Response.json({ rejected: [{ id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", status: "rejected" }] });
      }
      if (url.endsWith("/suggestions") && init?.method === "POST") {
        return Response.json({
          id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
          patient_id: JANE,
          request_id: REQUEST,
          kind: "plan_item",
          status: "pending",
          source: "research_add_to_plan",
          reason: "Recheck lipids in 6 weeks",
          citations: [],
        });
      }
      return Response.json({ suggestions: [] });
    };

    const client = createClient("http://api.test/");
    const pending = await client.listPending(JANE);
    assert.deepEqual(pending, []);
    const approved = await client.approve(["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]);
    assert.equal(approved.reminder_review.answer, "Screenings are up to date.");
    const rejected = await client.reject(["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"], "Not accurate");
    assert.equal(rejected[0]?.status, "rejected");
    const plan = await client.addToPlan(JANE, REQUEST, "Recheck lipids in 6 weeks", []);
    assert.equal(plan.source, "research_add_to_plan");
    assert.equal(plan.kind, "plan_item");

    assert.equal(calls[0]?.url, `http://api.test/suggestions?patient_id=${JANE}&status=pending`);
    assert.equal(calls[0]?.method, "GET");
    assert.deepEqual(calls[1]?.json, { suggestion_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"] });
    assert.equal(calls[1]?.url, "http://api.test/suggestions/approve");
    assert.deepEqual(calls[2]?.json, {
      suggestion_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
      reason: "Not accurate",
    });
    assert.deepEqual(calls[3]?.json, {
      patient_id: JANE,
      request_id: REQUEST,
      text: "Recheck lipids in 6 weeks",
      citations: [],
    });
  });
});
