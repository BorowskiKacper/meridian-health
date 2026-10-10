"use client";

import { create } from "zustand";
import { labDrafts, plan, runSearch, type Context, type Draft } from "./agent";
import { NOW_MINUTE, seedPatients } from "./data";
import type {
  Agent,
  AuditRow,
  ChartChange,
  Conversation,
  Layout,
  Message,
  Mode,
  Patient,
  ProposedAction,
  ResearchResult,
  Specialty,
  TabKind,
  WorkTab,
} from "./types";

let seq = 0;
const uid = (prefix: string) => `${prefix}-${++seq}`;

const AGENT_DELAY_MS = 650;

export interface PatientView {
  specialty: Specialty;
  minute: number;
}

interface State {
  patients: Record<string, Patient>;
  tabs: WorkTab[];
  activeTabId: string | null;
  conversations: Conversation[];
  activeConversationId: string | null;
  actions: ProposedAction[];
  research: Record<string, ResearchResult>;
  audit: AuditRow[];
  sms: Record<string, string>;
  views: Record<string, PatientView>;
  mode: Mode;
  layout: Layout;
  agentOpen: boolean;

  openTab: (kind: TabKind, patientId: string, refId?: string) => void;
  closeTab: (id: string) => void;
  activateTab: (id: string) => void;
  moveTab: (id: string, toIndex: number) => void;
  setView: (patientId: string, view: Partial<PatientView>) => void;

  newConversation: (patientId: string) => void;
  activateConversation: (id: string) => void;
  closeConversation: (id: string) => void;
  setMode: (mode: Mode) => void;
  setLayout: (layout: Layout) => void;
  setAgentOpen: (open: boolean) => void;

  send: (text: string) => void;
  reroute: (messageId: string, route: Agent) => void;
  approve: (id: string) => void;
  reject: (id: string) => void;
  approveMessage: (messageId: string) => void;

  extractLab: (patientId: string) => void;
  runReminders: (patientId: string) => void;
  optOut: (patientId: string) => void;
}

const initialTabs: WorkTab[] = [
  { id: "tab-body-nora", kind: "body", patientId: "nora" },
  { id: "tab-timeline-nora", kind: "timeline", patientId: "nora" },
  { id: "tab-queue-nora", kind: "queue", patientId: "nora" },
  { id: "tab-body-marcus", kind: "body", patientId: "marcus" },
];

const initialConversations: Conversation[] = [
  { id: "conv-nora", patientId: "nora", title: "Nora Ellison", messages: [] },
];

export const useStore = create<State>()((set, get) => {
  const contextFor = (patientId: string): Context => {
    const state = get();
    return {
      patient: state.patients[patientId]!,
      pending: state.actions.filter((a) => a.patientId === patientId && a.status === "pending"),
    };
  };

  const updateConversation = (id: string, fn: (c: Conversation) => Conversation) =>
    set((s) => ({ conversations: s.conversations.map((c) => (c.id === id ? fn(c) : c)) }));

  const updateMessage = (conversationId: string, messageId: string, patch: Partial<Message>) =>
    updateConversation(conversationId, (c) => ({
      ...c,
      messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
    }));

  const draftActions = (drafts: Draft[], patientId: string, conversationId: string, messageId: string): ProposedAction[] =>
    drafts.map((draft) => ({ ...draft, id: uid("act"), status: "pending", patientId, conversationId, messageId }));

  const audit = (patientId: string, action: AuditRow["action"], detail: string) =>
    set((s) => ({ audit: [...s.audit, { id: uid("audit"), patientId, action, detail }] }));

  const conversationFor = (patientId: string): string => {
    const state = get();
    const active = state.conversations.find((c) => c.id === state.activeConversationId);
    if (active?.patientId === patientId) return active.id;
    const existing = state.conversations.find((c) => c.patientId === patientId);
    if (existing) return existing.id;
    get().newConversation(patientId);
    return get().activeConversationId!;
  };

  const resolve = (conversationId: string, messageId: string, text: string, mode: Mode) => {
    const conversation = get().conversations.find((c) => c.id === conversationId);
    if (!conversation) return;
    const result = plan(text, mode, contextFor(conversation.patientId));
    const actions = draftActions(result.drafts, conversation.patientId, conversationId, messageId);
    set((s) => ({ actions: [...s.actions, ...actions] }));
    updateMessage(conversationId, messageId, {
      text: result.reply,
      route: result.route,
      routedBy: result.routedBy,
      requestText: text,
      pending: false,
    });
  };

  const applyChange = (patient: Patient, change: ChartChange): Patient => {
    switch (change.type) {
      case "add_finding":
        if (patient.findings.some((f) => f.id === change.finding.id)) return patient;
        return { ...patient, findings: [...patient.findings, { ...change.finding, meds: [...change.finding.meds] }] };
      case "add_med": {
        const host = patient.findings.find((f) => f.id === change.findingId);
        if (!host) {
          return { ...patient, notes: [...patient.notes, { id: uid("note"), minute: NOW_MINUTE, text: `Medication: ${change.med}` }] };
        }
        return {
          ...patient,
          findings: patient.findings.map((f) =>
            f.id === host.id ? { ...f, meds: [...f.meds.filter((m) => !/^No /.test(m)), change.med] } : f,
          ),
        };
      }
      case "add_note":
        return { ...patient, notes: [...patient.notes, { id: uid("note"), minute: NOW_MINUTE, text: change.text, findingId: change.findingId }] };
      case "add_family":
        return patient.family.includes(change.text) ? patient : { ...patient, family: [...patient.family, change.text] };
      case "update_reminder":
        return {
          ...patient,
          reminders: patient.reminders.map((r) => (r.id === change.reminderId ? { ...r, detail: change.detail, status: "due" } : r)),
        };
    }
  };

  return {
    patients: Object.fromEntries(seedPatients.map((p) => [p.id, p])),
    tabs: initialTabs,
    activeTabId: initialTabs[0]!.id,
    conversations: initialConversations,
    activeConversationId: initialConversations[0]!.id,
    actions: [],
    research: {},
    audit: [],
    sms: {},
    views: Object.fromEntries(seedPatients.map((p) => [p.id, { specialty: "all", minute: NOW_MINUTE }])),
    mode: "auto",
    layout: "split",
    agentOpen: true,

    openTab: (kind, patientId, refId) => {
      const existing = get().tabs.find((t) => t.kind === kind && t.patientId === patientId && t.refId === refId);
      if (existing) {
        set({ activeTabId: existing.id });
        return;
      }
      const tab: WorkTab = { id: uid("tab"), kind, patientId, refId };
      set((s) => ({
        tabs: [...s.tabs, tab],
        activeTabId: tab.id,
        layout: s.layout === "agent" ? "split" : s.layout,
      }));
    },

    closeTab: (id) =>
      set((s) => {
        const index = s.tabs.findIndex((t) => t.id === id);
        const tabs = s.tabs.filter((t) => t.id !== id);
        const activeTabId = s.activeTabId === id ? (tabs[Math.max(0, index - 1)]?.id ?? null) : s.activeTabId;
        return { tabs, activeTabId };
      }),

    activateTab: (id) => set({ activeTabId: id }),

    moveTab: (id, toIndex) =>
      set((s) => {
        const tabs = [...s.tabs];
        const from = tabs.findIndex((t) => t.id === id);
        if (from < 0) return {};
        const [tab] = tabs.splice(from, 1);
        tabs.splice(Math.min(toIndex, tabs.length), 0, tab!);
        return { tabs };
      }),

    setView: (patientId, view) =>
      set((s) => ({ views: { ...s.views, [patientId]: { ...s.views[patientId]!, ...view } } })),

    newConversation: (patientId) => {
      const conversation: Conversation = {
        id: uid("conv"),
        patientId,
        title: get().patients[patientId]!.name,
        messages: [],
      };
      set((s) => ({ conversations: [...s.conversations, conversation], activeConversationId: conversation.id, agentOpen: true }));
    },

    activateConversation: (id) => set({ activeConversationId: id }),

    closeConversation: (id) =>
      set((s) => {
        const index = s.conversations.findIndex((c) => c.id === id);
        const conversations = s.conversations.filter((c) => c.id !== id);
        const activeConversationId =
          s.activeConversationId === id ? (conversations[Math.max(0, index - 1)]?.id ?? null) : s.activeConversationId;
        return {
          conversations,
          activeConversationId,
          tabs: s.tabs.filter((t) => !(t.kind === "chat" && t.refId === id)),
        };
      }),

    setMode: (mode) => set({ mode }),
    setLayout: (layout) => set({ layout, agentOpen: layout === "workspace" ? get().agentOpen : true }),
    setAgentOpen: (agentOpen) => set({ agentOpen }),

    send: (text) => {
      const state = get();
      let conversationId = state.activeConversationId;
      if (!conversationId) {
        const tab = state.tabs.find((t) => t.id === state.activeTabId);
        get().newConversation(tab?.patientId ?? seedPatients[0]!.id);
        conversationId = get().activeConversationId!;
      }
      const doctor: Message = { id: uid("msg"), role: "doctor", text };
      const reply: Message = { id: uid("msg"), role: "agent", text: "", pending: true };
      updateConversation(conversationId, (c) => ({ ...c, messages: [...c.messages, doctor, reply] }));
      const mode = state.mode;
      setTimeout(() => resolve(conversationId!, reply.id, text, mode), AGENT_DELAY_MS);
    },

    reroute: (messageId, route) => {
      const conversation = get().conversations.find((c) => c.messages.some((m) => m.id === messageId));
      const message = conversation?.messages.find((m) => m.id === messageId);
      if (!conversation || !message?.requestText) return;
      const dropped = get().actions.filter((a) => a.messageId === messageId && a.status === "pending");
      if (dropped.length) {
        set((s) => ({
          actions: s.actions.map((a) => (a.messageId === messageId && a.status === "pending" ? { ...a, status: "rejected" } : a)),
        }));
        audit(conversation.patientId, "Discarded", `${dropped.length} pending item(s) when the request was re-routed to ${route}.`);
      }
      updateMessage(conversation.id, messageId, { pending: true, text: "" });
      const text = message.requestText;
      setTimeout(() => resolve(conversation.id, messageId, text, route), AGENT_DELAY_MS);
    },

    approve: (id) => {
      const action = get().actions.find((a) => a.id === id && a.status === "pending");
      if (!action) return;
      set((s) => ({ actions: s.actions.map((a) => (a.id === id ? { ...a, status: "approved" } : a)) }));
      audit(action.patientId, "Approved", action.title);

      const { payload } = action;
      if (payload.kind === "open_tab") {
        get().openTab(payload.tab, action.patientId, payload.refId);
        return;
      }
      if (payload.kind === "chart_change") {
        set((s) => ({
          patients: { ...s.patients, [action.patientId]: applyChange(s.patients[action.patientId]!, payload.change) },
        }));
        return;
      }

      const outcome = runSearch(action, contextFor(action.patientId));
      const result: ResearchResult = { ...outcome.result, id: uid("research") };
      const reply: Message = {
        id: uid("msg"),
        role: "agent",
        text: outcome.reply,
        route: action.agent,
        routedBy: "auto",
        researchId: result.id,
      };
      const followups = draftActions(outcome.drafts, action.patientId, action.conversationId, reply.id);
      set((s) => ({ research: { ...s.research, [result.id]: result }, actions: [...s.actions, ...followups] }));
      updateConversation(action.conversationId, (c) => ({ ...c, messages: [...c.messages, reply] }));
    },

    reject: (id) => {
      const action = get().actions.find((a) => a.id === id && a.status === "pending");
      if (!action) return;
      set((s) => ({ actions: s.actions.map((a) => (a.id === id ? { ...a, status: "rejected" } : a)) }));
      audit(action.patientId, "Rejected", `${action.title}. Nothing changed.`);
    },

    approveMessage: (messageId) => {
      for (const action of get().actions.filter((a) => a.messageId === messageId && a.status === "pending")) {
        get().approve(action.id);
      }
    },

    extractLab: (patientId) => {
      const conversationId = conversationFor(patientId);
      const message: Message = {
        id: uid("msg"),
        role: "agent",
        text: "I read the photographed panel and drafted the flagged values. Approve the ones you want on the chart.",
        route: "chart",
        routedBy: "auto",
      };
      const actions = draftActions(labDrafts(get().patients[patientId]!), patientId, conversationId, message.id);
      updateConversation(conversationId, (c) => ({ ...c, messages: [...c.messages, message] }));
      set((s) => ({ actions: [...s.actions, ...actions], activeConversationId: conversationId, agentOpen: true }));
    },

    runReminders: (patientId) => {
      const patient = get().patients[patientId]!;
      const due = patient.reminders.filter((r) => r.status === "due");
      if (!patient.smsOptIn) {
        set((s) => ({ sms: { ...s.sms, [patientId]: "The patient has opted out. Nothing was sent." } }));
        return;
      }
      if (!due.length) {
        set((s) => ({ sms: { ...s.sms, [patientId]: "Nothing is due on the simulated date." } }));
        return;
      }
      set((s) => ({
        patients: {
          ...s.patients,
          [patientId]: { ...patient, reminders: patient.reminders.map((r) => (r.status === "due" ? { ...r, status: "sent" } : r)) },
        },
        sms: { ...s.sms, [patientId]: "You have a reminder from your care team. Call 555-0100 to schedule." },
      }));
      audit(patientId, "SMS", `${due.length} reminder(s) sent with no health details.`);
    },

    optOut: (patientId) => {
      set((s) => ({
        patients: { ...s.patients, [patientId]: { ...s.patients[patientId]!, smsOptIn: false } },
        sms: { ...s.sms, [patientId]: "STOP received. SMS is off for this patient." },
      }));
      audit(patientId, "Opt-out", "Patient replied STOP.");
    },
  };
});
