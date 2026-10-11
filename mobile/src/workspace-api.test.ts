import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { workspaceClient } from './workspace-api';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('pairing uses the deployed API and requests do not infer a patient', async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = async (url, init) => { calls.push({ url: String(url), init }); return new Response(JSON.stringify({ token: 'device', id: 'submission', status: 'queued' })); };
  const client = workspaceClient('https://api.example/');
  await client.pair('ABCD1234');
  await client.submit('device', 'submission', 'Open a chart');
  assert.equal(calls[0].url, 'https://api.example/workspaces/pair');
  assert.equal(calls[1].url, 'https://api.example/workspaces/requests');
  assert.equal((calls[1].init?.headers as Record<string, string>).Authorization, 'Bearer device');
  const form = calls[1].init?.body as FormData;
  assert.equal(form.get('patient_id'), null);
  assert.equal(form.get('submission_id'), 'submission');
});

test('retry preserves submission identity and explicit conversation patient', async () => {
  const forms: FormData[] = [];
  globalThis.fetch = async (_url, init) => { forms.push(init?.body as FormData); return new Response(JSON.stringify({ id: 'same', status: 'queued' })); };
  const client = workspaceClient('https://api.example');
  await client.submit('device', 'same', 'Follow-up question', undefined, 'patient');
  await client.submit('device', 'same', 'Follow-up question', undefined, 'patient');
  assert.equal(forms[0].get('submission_id'), forms[1].get('submission_id'));
  assert.equal(forms[0].get('patient_id'), 'patient');
});

test('voice and patient clarification remain distinct requests', async () => {
  const calls: { url: string; body: BodyInit | null | undefined }[] = [];
  globalThis.fetch = async (url, init) => { calls.push({ url: String(url), body: init?.body }); return new Response(JSON.stringify({ id: 'job', status: 'queued' })); };
  const client = workspaceClient('https://api.example');
  await client.submit('device', 'job', undefined, new Blob(['audio'], { type: 'audio/mp4' }));
  const form = calls[0].body as FormData;
  assert.ok(form.get('audio'));
  assert.equal(form.get('text'), null);
  await client.clarify('device', 'job', 'Amy Lee');
  assert.equal(calls[1].url, 'https://api.example/workspaces/requests/job/clarify');
  assert.equal(JSON.parse(calls[1].body as string).text, 'Amy Lee');
});

test('revoked pairing produces a recognizable authentication error', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Device disconnected' }), { status: 401 });
  await assert.rejects(workspaceClient('https://api.example').state('device'), (error: unknown) => error instanceof Error && 'status' in error && error.status === 401);
});
