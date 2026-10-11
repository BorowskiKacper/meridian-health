import assert from 'node:assert/strict';
import { test } from 'node:test';
import { deliveryStatus } from './workspace-status';
import type { WorkspaceJob } from './workspace-api';

const job: WorkspaceJob = { id: 'job', status: 'completed', text: 'Open vitals', patient_id: 'patient', patient_name: 'Amy', desktop_applied: false, navigation: [{ patient_id: 'patient', view: 'vitals' }] };
test('navigation waits for a display receipt before saying opened', () => {
  assert.equal(deliveryStatus(job), 'Waiting for laptop to open the view');
  assert.equal(deliveryStatus({ ...job, desktop_applied: true }), 'Opened on laptop');
});
test('chart drafts never claim a view was opened', () => {
  assert.equal(deliveryStatus({ ...job, navigation: [], desktop_applied: true }), 'Available on laptop');
});
