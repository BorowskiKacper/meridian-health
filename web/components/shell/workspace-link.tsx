"use client";

import { useEffect, useRef, useState } from 'react';
import { Smartphone, X } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { useStore } from '@/lib/store';
import { connectWorkspace, setWorkspaceToken, workspaceApi, type WorkspaceJob, type WorkspaceState } from '@/lib/workspace-api';
import type { TabKind } from '@/lib/types';
import { waitForWorkspaceDisplay } from '@/lib/workspace-display';

export function WorkspaceLink() {
  const [paired, setPaired] = useState(false);
  const [connected, setConnected] = useState(false);
  const [shown, setShown] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const cursor = useRef(0);
  const status = useStore((s) => s.status);
  useEffect(() => {
    if (status !== 'ready') return;
    let stopped = false;
    let initialized = false;
    let applying = false;
    let polling = false;
    const deliveries = new Map<string, { job: WorkspaceJob; tabId: string | null }>();
    const acknowledged = new Set<string>();
    let timer: ReturnType<typeof setTimeout>;
    let saveTimer: ReturnType<typeof setTimeout>;
    let writes = Promise.resolve();
    const save = () => {
      const s = useStore.getState();
      const tabs = s.tabs.filter((t) => t.kind !== 'research' || s.workspaceJobs[t.refId ?? '']);
      const body = JSON.stringify({ cursor: cursor.current, tabs, activeTabId: tabs.some((t) => t.id === s.activeTabId) ? s.activeTabId : tabs[0]?.id ?? null });
      writes = writes.catch(() => {}).then(async () => {
        if (!stopped) await workspaceApi('/snapshot', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body });
      });
      return writes;
    };
    const acknowledge = async (job: WorkspaceJob, tabId: string | null) => {
      if (stopped || job.desktop_applied || acknowledged.has(job.id) || !await waitForWorkspaceDisplay(tabId, job.id)) return;
      try {
        await workspaceApi(`/requests/${job.id}/acknowledge`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tab_id: tabId }) });
        deliveries.delete(job.id);
        acknowledged.add(job.id);
      } catch { /* Retry delivery acknowledgement without replaying the navigation. */ }
    };
    const consume = async (state: WorkspaceState, first: boolean) => {
      if (stopped) return;
      applying = true;
      setPaired(state.paired);
      if (first && !state.snapshot) cursor.current = 0;
      if (first && state.snapshot) {
        for (const tab of state.snapshot.tabs) {
          if (tab.patientId && !useStore.getState().patients[tab.patientId]) await useStore.getState().refreshPatient(tab.patientId);
          if (tab.kind === 'research' && tab.refId && !useStore.getState().research[tab.refId]) {
            const job = await workspaceApi<WorkspaceJob>(`/requests/${tab.refId}`);
            await useStore.getState().syncWorkspaceJob(job);
          }
        }
        useStore.setState({ tabs: state.snapshot.tabs, activeTabId: state.snapshot.activeTabId });
        cursor.current = state.snapshot.cursor;
      }
      for (const event of state.events.filter((e) => e.sequence > cursor.current)) {
        if (event.kind === 'queued' && event.job_id) {
          const job = state.jobs.find((j) => j.id === event.job_id);
          if (job) await useStore.getState().syncWorkspaceJob(job);
          const conversation = useStore.getState().conversations.find((c) => c.messages.some((m) => m.workspaceJobId === event.job_id));
          if (conversation) useStore.getState().activateConversation(conversation.id);
        }
        if (event.kind === 'completed' && event.job_id) {
          const job = state.jobs.find((j) => j.id === event.job_id) ?? await workspaceApi<WorkspaceJob>(`/requests/${event.job_id}`);
          await useStore.getState().syncWorkspaceJob(job);
          if (job.response?.answer && job.response.route === 'clinical_question') {
            useStore.getState().openTab('research', job.patient_id ?? '', job.id);
          }
          for (const command of job.navigation ?? []) {
            useStore.getState().openTab(command.view as TabKind, command.patient_id);
          }
          const hasView = Boolean(job.navigation?.length || (job.response?.answer && job.response.route === 'clinical_question'));
          if (hasView && useStore.getState().layout === 'agent') useStore.getState().setLayout('split');
          const conversation = useStore.getState().conversations.find((c) => c.messages.some((m) => m.workspaceJobId === job.id));
          if (conversation) useStore.getState().activateConversation(conversation.id);
          cursor.current = event.sequence;
          const tabId = hasView ? useStore.getState().activeTabId : null;
          deliveries.set(job.id, { job, tabId });
          await save();
          await acknowledge(job, tabId);
        }
        if (event.kind === 'chart_changed') {
          const patients = new Set(state.jobs.map((j) => j.patient_id).filter((id): id is string => Boolean(id)));
          for (const id of patients) await useStore.getState().refreshPatient(id);
        }
        cursor.current = event.sequence;
      }
      initialized = true;
      applying = false;
      if (first || cursor.current > (state.snapshot?.cursor ?? 0)) await save();
      // History reconciliation cannot delay opening the newly requested view.
      for (const job of state.jobs) {
        if (job.desktop_applied) deliveries.delete(job.id);
        if (job.patient_id && !useStore.getState().patients[job.patient_id]) continue;
        await useStore.getState().syncWorkspaceJob(job);
      }
      if (first) {
        const s = useStore.getState();
        const active = s.tabs.find((t) => t.id === s.activeTabId);
        for (const job of state.jobs.filter((j) => j.status === 'completed' && !j.desktop_applied && !acknowledged.has(j.id))) {
          const last = job.navigation?.at(-1);
          if ((last && active?.kind === last.view && active.patientId === last.patient_id) || (active?.kind === 'research' && active.refId === job.id)) deliveries.set(job.id, { job, tabId: active?.id ?? null });
        }
      }
      for (const { job, tabId } of deliveries.values()) {
        if (tabId !== null && tabId !== useStore.getState().activeTabId) continue;
        if (tabId === null && !useStore.getState().conversations.find((c) => c.id === useStore.getState().activeConversationId)?.messages.some((m) => m.workspaceJobId === job.id)) continue;
        await acknowledge(job, tabId);
      }
    };
    const tick = async () => {
      if (stopped || polling) return;
      polling = true;
      try {
        const state = initialized ? await workspaceApi<WorkspaceState>(`/state?after=${cursor.current}`) : await connectWorkspace();
        await consume(state, !initialized);
        if (!stopped) { setConnected(true); setError(''); }
      } catch (e) {
        applying = false;
        if (!stopped) setConnected(false);
        if (e instanceof ApiError && e.status === 401) { setWorkspaceToken(null); initialized = false; }
      } finally {
        polling = false;
        if (!stopped) timer = setTimeout(() => void tick(), document.visibilityState === 'visible' ? 1000 : 10000);
      }
    };
    const unsubscribe = useStore.subscribe((s, before) => {
      if (!initialized || applying || (s.tabs === before.tabs && s.activeTabId === before.activeTabId)) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => { void save().catch(() => setConnected(false)); }, 200);
    });
    const foreground = () => { if (document.visibilityState === 'visible') { clearTimeout(timer); void tick(); } };
    document.addEventListener('visibilitychange', foreground);
    void tick();
    return () => { stopped = true; clearTimeout(timer); clearTimeout(saveTimer); unsubscribe(); document.removeEventListener('visibilitychange', foreground); };
  }, [status]);

  const showCode = async () => {
    setShown(true); setError(''); setBusy(true);
    try {
      const result = await workspaceApi<{ code: string }>('/pairing-code', { method: 'POST' });
      setCode(result.code);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create a pairing code.'); }
    finally { setBusy(false); }
  };
  return <div className="relative ml-auto shrink-0">
    <button type="button" onClick={() => paired ? setShown(!shown) : void showCode()} className="flex h-9 items-center gap-2 rounded-md px-3 text-[13px] text-jade-900 hover:bg-jade-100 focus-visible:ring-2 focus-visible:ring-jade-600" aria-expanded={shown}><Smartphone className="size-4" />{paired ? connected ? 'Phone connected' : 'Reconnecting' : 'Connect phone'}</button>
    {shown && <div className="absolute top-11 right-0 z-50 w-72 rounded-lg border border-hairline-strong bg-clinical-surface p-5 shadow-lg">
      <div className="flex items-center justify-between"><p className="text-[14px] font-semibold">{paired ? 'Paired phone' : 'Connect your phone'}</p><button type="button" aria-label="Close pairing" onClick={() => setShown(false)} className="rounded p-1 hover:bg-jade-100"><X className="size-4" /></button></div>
      {paired ? <><p className="mt-3 text-[13px] text-ink-soft">Prompts and results are shared. Pairing stays active until you disconnect.</p><button type="button" disabled={busy} className="mt-4 text-[13px] text-critical hover:underline" onClick={() => { setBusy(true); void workspaceApi('/disconnect', { method: 'POST' }).then(() => { setPaired(false); setCode(''); }).catch((e) => setError(String(e))).finally(() => setBusy(false)); }}>Disconnect phone</button></> : <><p className="mt-3 text-[13px] text-ink-soft">Enter this code in the Meridian mobile app.</p><p className="mt-4 text-center font-mono text-2xl tracking-widest">{busy ? '…' : code}</p><p className="mt-3 text-[12px] text-ink-faint">The unused code lasts five minutes. Pairing does not expire.</p><button type="button" disabled={busy} className="mt-3 text-[13px] text-jade-700 hover:underline" onClick={() => void showCode()}>Generate another code</button></>}
      {error && <p role="alert" className="mt-3 text-[13px] text-critical">{error}</p>}
    </div>}
  </div>;
}
