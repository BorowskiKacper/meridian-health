import type { WorkspaceJob } from './workspace-api';

export function deliveryStatus(job: WorkspaceJob): string {
  if (job.navigation?.length) return job.desktop_applied ? 'Opened on laptop' : 'Waiting for laptop to open the view';
  if (job.response?.route === 'clinical_question' && job.response.answer) return job.desktop_applied ? 'Research displayed on laptop' : 'Research ready; waiting for laptop';
  return job.desktop_applied ? 'Available on laptop' : 'Ready for your laptop';
}
