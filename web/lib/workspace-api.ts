import { api, type DoctorRequest, type RequestRoute } from './api';

export interface WorkspaceJob {
  id: string;
  status: 'queued' | 'running' | 'needs_patient' | 'completed' | 'failed';
  text: string;
  patient_id: string | null;
  patient_name: string | null;
  desktop_applied: boolean;
  error?: string;
  question?: string;
  candidates?: { id: string; display_name: string; date_of_birth: string }[];
  response?: Omit<DoctorRequest, 'route'> & { route: DoctorRequest['route'] | 'navigate' };
  navigation?: { patient_id: string; view: string }[];
}
export interface WorkspaceState {
  paired: boolean;
  cursor: number;
  events: { sequence: number; kind: string; job_id: string | null }[];
  jobs: WorkspaceJob[];
  snapshot: { cursor: number; tabs: import('./types').WorkTab[]; activeTabId: string | null } | null;
}
let token: string | null = null;
export const getWorkspaceToken = () => token;
export function setWorkspaceToken(value: string | null) {
  token = value;
  if (typeof window !== 'undefined') {
    if (value) localStorage.setItem('meridian-device', value);
    else localStorage.removeItem('meridian-device');
  }
}
export async function workspaceApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  return api<T>(`/workspaces${path}`, { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } });
}
export async function connectWorkspace() {
  token = localStorage.getItem('meridian-device');
  if (!token) {
    const result = await api<{ token: string }>('/workspaces', { method: 'POST' });
    setWorkspaceToken(result.token);
  }
  return workspaceApi<WorkspaceState>('/state');
}
export function submitWorkspace(text: string, audio?: Blob, patientId?: string | null, route?: RequestRoute, id = crypto.randomUUID()) {
  const form = new FormData();
  form.set('submission_id', id);
  if (audio) form.set('audio', audio, 'dictation.webm'); else form.set('text', text);
  if (patientId) form.set('patient_id', patientId);
  if (route) form.set('route', route);
  return workspaceApi<WorkspaceJob>('/requests', { method: 'POST', body: form });
}
export function clarifyWorkspace(jobId: string, text: string, patientId?: string) {
  return workspaceApi<WorkspaceJob>(`/requests/${jobId}/clarify`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, patient_id: patientId }) });
}
export function clarifyWorkspaceVoice(jobId: string, audio: Blob) {
  const form = new FormData();
  form.set('audio', audio, 'dictation.webm');
  return workspaceApi<WorkspaceJob>(`/requests/${jobId}/clarify-voice`, { method: 'POST', body: form });
}
