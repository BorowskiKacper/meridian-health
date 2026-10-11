import { ApiError, type AudioPart } from './api';
import type { DoctorRequest } from './types';

export interface WorkspaceJob {
  id: string;
  status: 'queued' | 'running' | 'needs_patient' | 'completed' | 'failed';
  text: string;
  patient_id: string | null;
  patient_name: string | null;
  desktop_applied: boolean;
  question?: string;
  candidates?: { id: string; display_name: string; date_of_birth: string }[];
  error?: string;
  response?: DoctorRequest;
  navigation?: { patient_id: string; view: string }[];
}
export interface WorkspaceState { paired: boolean; cursor: number; jobs: WorkspaceJob[]; patient_name: string | null }

export function workspaceClient(root: string) {
  const request = async <T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(`${root.replace(/\/$/, '')}/workspaces${path}`, { ...init, signal: controller.signal, headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
      const body = await response.json();
      if (!response.ok) throw new ApiError(response.status, 'workspace_error', body.error?.message ?? body.detail ?? 'Request could not complete.');
      return body as T;
    } finally { clearTimeout(timer); }
  };
  const json = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
  return {
    pair: (code: string) => request<{ token: string }>('/pair', null, json({ code })),
    state: (token: string) => request<WorkspaceState>('/state', token),
    disconnect: (token: string) => request('/disconnect', token, { method: 'POST' }),
    clarify: (token: string, job: string, text: string, patientId?: string) => request<WorkspaceJob>(`/requests/${job}/clarify`, token, json({ text, patient_id: patientId })),
    clarifyVoice: (token: string, job: string, audio: AudioPart) => {
      const body = new FormData(); body.append('audio', audio as Blob);
      return request<WorkspaceJob>(`/requests/${job}/clarify-voice`, token, { method: 'POST', body });
    },
    submit: (token: string, id: string, text?: string, audio?: AudioPart, patientId?: string | null) => {
      const body = new FormData();
      body.append('submission_id', id);
      if (patientId) body.append('patient_id', patientId);
      if (audio) body.append('audio', audio as Blob); else body.append('text', text ?? '');
      return request<WorkspaceJob>('/requests', token, { method: 'POST', body });
    },
    approve: (token: string, ids: string[]) => request('/approve', token, json({ suggestion_ids: ids })),
    reject: (token: string, ids: string[], reason: string) => request('/reject', token, json({ suggestion_ids: ids, reason })),
  };
}
