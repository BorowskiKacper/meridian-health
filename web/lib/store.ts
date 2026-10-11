"use client";

import { create } from "zustand";
import { ApiError } from "./api";
import { approveSuggestions, createPlanItem, getCapabilities, postGeneralChat, postRequest, postVoiceRequest, previewRequest, rejectSuggestions, runReminderJob, sendStop, uploadDocument, type Capabilities, type DocumentResult, type RequestRoute } from "./api";
import { loadWorkspace, reloadPatient, suggestionAction, todayIso } from "./chart";
import { NOW_MINUTE } from "./data";
import type {
  Agent,
  AuditRow,
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

const OPEN_TAB: Record<string, TabKind> = {
  "open the overview": "overview",
  "open the vitals": "vitals",
  "open the medications": "medications",
  "open the allergies": "allergies",
  "open the timeline": "timeline",
  "open the approvals": "queue",
  "open the lab report": "lab",
  "open the lab": "lab",
  "open the reminders": "reminders",
  "open the body": "body",
};

const ROUTE_LABEL = {
  chart_update: "chart",
  clinical_question: "research",
  check_screenings: "screening",
} as const;

export interface PatientView {
  specialty: Specialty;
  minute: number;
}

interface State {
  routePreviews: Record<string, { status: "checking" | "ready" | "error"; text: string; audio?: Blob; route?: RequestRoute; description?: string; error?: string }>;
  cancelRoutePreview: (conversationId: string) => void;
  confirmRoutePreview: (conversationId: string, route?: RequestRoute) => void;
  sendConfirmed: (text: string, audio?: Blob, route?: RequestRoute, conversationId?: string, reviewedTranscript?: string) => void;
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
  status: "loading" | "ready" | "error";
  statusMessage: string;
  notice: string | null;
  uploadedLabs: Record<string, string>;
  capabilities: Capabilities | null;
  approvingIds: string[];
  approvalErrors: Record<string, string>;

  load: () => Promise<void>;
  refreshPatient: (patientId: string) => Promise<void>;
  openPatient: (patientId: string) => Promise<void>;
  openTab: (kind: TabKind, patientId: string, refId?: string) => void;
  closeTab: (id: string) => void;
  activateTab: (id: string) => void;
  moveTab: (id: string, toIndex: number) => void;
  setView: (patientId: string, view: Partial<PatientView>) => void;

  newConversation: (patientId: string) => void;
  activateConversation: (id: string) => void;
  setMode: (mode: Mode) => void;
  setLayout: (layout: Layout) => void;

  requestModes: Record<string, import("./api").RequestRoute | undefined>;
  setRequestMode: (conversationId: string, route?: import("./api").RequestRoute) => void;
  send: (text: string, audio?: Blob) => void;
  reroute: (messageId: string, route: Agent) => void;
  approve: (id: string) => void;
  approveSelected: (ids: string[]) => Promise<boolean>;
  reject: (id: string) => void;
  approveMessage: (messageId: string) => void;
  addToPlan: (researchId: string) => Promise<void>;

  extractLab: (patientId: string, file: File) => Promise<DocumentResult | undefined>;
  runReminders: (patientId: string) => void;
  optOut: (patientId: string) => void;
}

function explain(error: unknown, fallback: string): string {
  if (error instanceof ApiError && (error.status < 500 || error.status === 503)) return error.message;
  if (error instanceof Error && !(error instanceof ApiError) && error.message) return error.message;
  return fallback;
}

export const useStore = create<State>()((set, get) => {
  const updateConversation = (id: string, fn: (c: Conversation) => Conversation) =>
    set((s) => ({ conversations: s.conversations.map((c) => (c.id === id ? fn(c) : c)) }));

  const updateMessage = (conversationId: string, messageId: string, patch: Partial<Message>) =>
    updateConversation(conversationId, (c) => ({
      ...c,
      messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
    }));

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

  const replacePatient = (patient: Patient, actions: ProposedAction[]) =>
    set((s) => ({
      patients: { ...s.patients, [patient.id]: patient },
      actions: [
        ...s.actions.filter((action) => action.patientId !== patient.id),
        ...actions.map((action) => {
          const previous = s.actions.find((item) => item.id === action.id);
          return previous
            ? { ...action, conversationId: previous.conversationId, messageId: previous.messageId }
            : action;
        }),
      ],
      views: {
        ...s.views,
        [patient.id]: s.views[patient.id] ?? { specialty: "all", minute: NOW_MINUTE },
      },
    }));

  const refreshPatient = async (patientId: string) => {
    const loaded = await reloadPatient(patientId);
    replacePatient(loaded.patient, loaded.actions);
  };

  return {
    patients: {},
    tabs: [],
    activeTabId: null,
    conversations: [],
    activeConversationId: null,
    actions: [],
    research: {},
    audit: [],
    sms: {},
    views: {},
    mode: "auto",
    layout: "split",
    status: "loading",
    statusMessage: "Loading the chart…",
    notice: null,
    uploadedLabs: {},
    capabilities: null,
    approvingIds: [],
    approvalErrors: {},
    requestModes: {},
    routePreviews: {},
    cancelRoutePreview: (id) => set((s) => ({ routePreviews: Object.fromEntries(Object.entries(s.routePreviews).filter(([key]) => key !== id)) })),
    confirmRoutePreview: (id, chosenRoute) => {
      const preview = get().routePreviews[id];
      if (preview?.status !== "ready" || !preview.route) return;
      const route = chosenRoute ?? preview.route;
      if (get().requestModes[id]) get().setRequestMode(id, route);
      get().cancelRoutePreview(id);
      get().sendConfirmed(preview.text, preview.audio, route, id, preview.audio ? preview.text : undefined);
    },
    setRequestMode: (id, route) => set((s) => ({ requestModes: { ...s.requestModes, [id]: route } })),
    refreshPatient,
    openPatient: async (patientId) => {
      await refreshPatient(patientId);
      get().openTab("overview", patientId);
      const layout = get().layout;
      const conversationId = conversationFor(patientId);
      set({ activeConversationId: conversationId, layout });
    },

    load: async () => {
      set({ status: "loading", statusMessage: "Loading the chart…", notice: null });
      try {
        const [chart, capabilities] = await Promise.all([loadWorkspace(), getCapabilities().catch(() => null)]);
        const patients = Object.fromEntries(chart.patients.map((patient) => [patient.id, patient]));
        const first = chart.patients[0];
        const conversations: Conversation[] = [{ id: "general", patientId: null, title: "General", messages: [] }, ...chart.patients.map((patient) => ({
              id: `conv-${patient.id}`,
              patientId: patient.id,
              title: patient.name,
              messages: [],
            }))];
        const tabs: WorkTab[] = first
          ? (["overview"] as const).map((kind) => ({
              id: `tab-${kind}-${first.id}`,
              kind,
              patientId: first.id,
            }))
          : [];
        set({
          patients,
          capabilities,
          actions: chart.actions,
          views: Object.fromEntries(chart.patients.map((patient) => [patient.id, { specialty: "all" as const, minute: NOW_MINUTE }])),
          conversations,
          activeConversationId: conversations[0]?.id ?? null,
          tabs,
          activeTabId: tabs[0]?.id ?? null,
          status: "ready",
          statusMessage: "",
          notice: chart.patients.length ? null : "The clinic API returned no patients.",
        });
      } catch (error) {
        set({
          status: "error",
          statusMessage: explain(error, "The clinic API is not reachable. Start the backend, then try again."),
        });
      }
    },

    openTab: (kind, patientId, refId) => {
      const existing = get().tabs.find((t) => t.kind === kind && t.patientId === patientId && t.refId === refId);
      if (existing) {
        set((s) => ({ activeTabId: existing.id, layout: s.layout === "agent" ? "split" : s.layout }));
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
      set((s) => ({ conversations: [...s.conversations, conversation], activeConversationId: conversation.id, layout: s.layout === "workspace" ? "split" : s.layout }));
    },

    activateConversation: (id) => set({ activeConversationId: id }),

    setMode: (mode) => set({ mode }),
    setLayout: (layout) => set({ layout }),

    send: (text, audio) => {
      let id = get().activeConversationId;
      if (!id) {
        const state = get();
        const patientId = state.tabs.find((t) => t.id === state.activeTabId)?.patientId ?? Object.keys(state.patients)[0];
        if (!patientId) return;
        get().newConversation(patientId);
        id = get().activeConversationId!;
      }
      const conversation = get().conversations.find((c) => c.id === id);
      if (!conversation || conversation.messages.some((m) => m.pending) || get().routePreviews[id]?.status === "checking" || get().routePreviews[id]?.status === "ready") return;
      if (conversation.patientId === null) {
        get().sendConfirmed(text, audio, "clinical_question", id);
        return;
      }
      const patientId = conversation.patientId;
      const mode = get().requestModes[id];
      if (!mode && !audio && OPEN_TAB[text.trim().toLowerCase()]) {
        get().sendConfirmed(text, undefined, undefined, id);
        return;
      }
      const preview = { status: "checking" as const, text, audio };
      const conversationId = id;
      set((s) => ({ routePreviews: { ...s.routePreviews, [conversationId]: preview } }));
      void (async () => {
        try {
          const result = await previewRequest(patientId, text, audio);
          if (get().routePreviews[conversationId] !== preview) return;
          if (mode && mode === result.route) {
            get().cancelRoutePreview(conversationId);
            get().sendConfirmed(result.transcript, audio, mode, conversationId, audio ? result.transcript : undefined);
          } else {
            set((s) => ({ routePreviews: { ...s.routePreviews, [conversationId]: { status: "ready", text: result.transcript, audio, route: result.route, description: result.description } } }));
          }
        } catch (error) {
          if (get().routePreviews[conversationId] !== preview) return;
          set((s) => ({ routePreviews: { ...s.routePreviews, [conversationId]: { status: "error", text, audio, error: explain(error, "Could not determine the workflow. Try again; nothing was submitted.") } } }));
        }
      })();
    },

    sendConfirmed: (text, audio, routeOverride, conversationOverride, reviewedTranscript) => {
      const state = get();
      let conversationId = conversationOverride ?? state.activeConversationId;
      if (!conversationId) {
        const tab = state.tabs.find((t) => t.id === state.activeTabId);
        const patientId = tab?.patientId ?? Object.keys(state.patients)[0];
        if (!patientId) return;
        get().newConversation(patientId);
        conversationId = get().activeConversationId!;
      }
      const conversation = get().conversations.find((c) => c.id === conversationId);
      if (!conversation) return;
      if (conversation.messages.some((message) => message.pending)) return;
      const doctor: Message = { id: uid("msg"), role: "doctor", text };
      const reply: Message = { id: uid("msg"), role: "agent", text: "", pending: true, route: routeOverride ? ROUTE_LABEL[routeOverride] : undefined };
      updateConversation(conversationId, (c) => ({ ...c, messages: [...c.messages, doctor, reply] }));
      const requestMode = routeOverride ?? get().requestModes[conversationId];
      const localTab = audio || requestMode || !conversation.patientId ? undefined : OPEN_TAB[text.trim().toLowerCase()];
      if (localTab && conversation.patientId) {
        get().openTab(localTab, conversation.patientId);
        updateMessage(conversationId, reply.id, {
          text: "Opened it beside the chart.",
          route: "navigate",
          routedBy: "auto",
          requestText: text,
          pending: false,
        });
        return;
      }
      void (async () => {
        try {
          const result = conversation.patientId === null ? await postGeneralChat(text, audio) : audio ? await postVoiceRequest(conversation.patientId, audio, requestMode, reviewedTranscript) : await postRequest(conversation.patientId, text, requestMode);
          if (audio) updateMessage(conversationId, doctor.id, { text: result.transcript || "Voice request (no transcript returned)" });
          const route = ROUTE_LABEL[result.route];
          const researchId = result.answer && result.route === "clinical_question" ? uid("research") : undefined;
          if (result.answer && researchId) {
            const answer = result.answer;
            set((s) => ({
              research: {
                ...s.research,
                [researchId]: {
                  id: researchId,
                  patientId: conversation.patientId,
                  question: result.transcript || text,
                  answer: answer.text,
                  basis: "",
                  sections: answer.sections,
                  requestId: result.request_id ?? null,
                  apiCitations: answer.citations,
                  citations: answer.citations.map((citation) => ({
                    source: citation.title || citation.source_id || "Source",
                    passage: citation.passage || "",
                    id: citation.source_id,
                    tier: citation.tier,
                    locator: citation.locator,
                  })),
                },
              },
            }));
          }
          const linked = (conversation.patientId ? result.suggestions : []).map((row) =>
            suggestionAction(row, { conversationId, messageId: reply.id }),
          );
          set((s) => ({
            actions: [...s.actions.filter((action) => !linked.some((item) => item.id === action.id)), ...linked],
          }));
          const replyText = result.answer
            ? result.answer.text
            : linked.length
              ? `Drafted ${linked.length} chart change${linked.length === 1 ? "" : "s"}. Nothing is written until you approve.`
              : "Nothing new was proposed.";
          updateMessage(conversationId, reply.id, {
            text: replyText,
            route,
            routedBy: "auto",
            requestText: text,
            researchId,
            audioBase64: result.audio_base64 ?? undefined,
            pending: false,
          });
          if (conversation.patientId) {
            try { await refreshPatient(conversation.patientId); } catch { set({ notice: "The request completed, but the chart could not refresh. Reload before continuing." }); }
          }
        } catch (error) {
          updateMessage(conversationId, reply.id, {
            text: explain(error, "The assistant request could not finish. Try again; no chart changes were approved."),
            error: true,
            requestText: text,
            pending: false,
          });
        }
      })();
    },

    reroute: (messageId, route) => {
      const conversation = get().conversations.find((c) => c.messages.some((m) => m.id === messageId));
      const message = conversation?.messages.find((m) => m.id === messageId);
      if (!conversation || !message?.requestText) return;
      updateMessage(conversation.id, messageId, {
        text: `The clinic API chooses the route from the text. This request was already sent as ${message.route ?? "a chart request"}, not as ${route}.`,
        pending: false,
      });
    },

    approve: (id) => { void get().approveSelected([id]); },

    approveSelected: async (ids) => {
      const uniqueIds = [...new Set(ids)];
      const selected = uniqueIds.map((id) => get().actions.find((a) => a.id === id && a.status === "pending"));
      const action = selected[0];
      if (!action || selected.some((a) => !a || a.patientId !== action.patientId)) return false;
      if (get().actions.some((a) => a.patientId === action.patientId && get().approvingIds.includes(a.id))) return false;
      set((s) => ({ approvingIds: [...s.approvingIds, ...uniqueIds], approvalErrors: Object.fromEntries(Object.entries(s.approvalErrors).filter(([id]) => !uniqueIds.includes(id))), notice: null }));
      let persisted = false;
        try {
          const result = await approveSuggestions(uniqueIds);
          persisted = true;
          const approvedIds = new Set(result.approved.map((row) => row.id));
          set((s) => ({ actions: s.actions.map((a) => approvedIds.has(a.id) ? { ...a, status: "approved" } : a) }));
          audit(action.patientId, "Approved", selected.length === 1 ? action.title : `${selected.length} reviewed chart changes.`);
          await refreshPatient(action.patientId);
          set({ notice: null });
          return true;
        } catch (error) {
          const message = persisted ? "Changes were approved, but the chart could not refresh. Reload before continuing." : explain(error, "Approval could not be confirmed. Reload the chart before retrying.");
          set((s) => ({
            notice: message,
            approvalErrors: { ...s.approvalErrors, ...Object.fromEntries(uniqueIds.map((id) => [id, message])) },
          }));
          return persisted;
        } finally {
          set((s) => ({ approvingIds: s.approvingIds.filter((id) => !uniqueIds.includes(id)) }));
        }
    },

    reject: (id) => {
      const action = get().actions.find((a) => a.id === id && a.status === "pending");
      if (!action) return;
      if (get().actions.some((a) => a.patientId === action.patientId && get().approvingIds.includes(a.id))) return;
      void (async () => {
        try {
          await rejectSuggestions([id], "Not accurate");
          audit(action.patientId, "Rejected", `${action.title}. Nothing changed.`);
          await refreshPatient(action.patientId);
          set({ notice: null });
        } catch (error) {
          set({ notice: explain(error, "The rejection did not reach the clinic API.") });
        }
      })();
    },

    approveMessage: (messageId) => {
      const ids = get()
        .actions.filter((a) => a.messageId === messageId && a.status === "pending")
        .map((a) => a.id);
      if (!ids.length) return;
      void get().approveSelected(ids);
    },

    addToPlan: async (researchId) => {
      const result = get().research[researchId];
      const text = result?.answer.trim();
      const patientId = result?.patientId;
      if (!result || !patientId || !text || result.plan?.status === "saving" || result.plan?.status === "added") return;
      const setPlan = (plan: ResearchResult["plan"]) => set((s) => ({ research: { ...s.research, [researchId]: { ...s.research[researchId]!, plan } } }));
      setPlan({ status: "saving" });
      let row;
      try {
        row = await createPlanItem(patientId, result.requestId ?? null, text, result.apiCitations ?? []);
      } catch (error) {
        setPlan({ status: "error", message: explain(error, "The plan item could not be added. Try again.") });
        return;
      }
      const action = suggestionAction(row);
      set((s) => ({ actions: [...s.actions.filter((a) => a.id !== action.id), action] }));
      setPlan({ status: "added", message: "Added as a suggestion awaiting approval." });
      try { await refreshPatient(patientId); }
      catch { setPlan({ status: "added", message: "Added as a suggestion awaiting approval. The chart could not refresh." }); }
    },

    extractLab: async (patientId, file) => {
      const patient = get().patients[patientId];
      if (!patient) return;
      const conversationId = conversationFor(patientId);
        try {
          const result = await uploadDocument(patientId, file);
          set((s) => ({ uploadedLabs: { ...s.uploadedLabs, [patientId]: result.document_id } }));
          const message: Message = {
            id: uid("msg"),
            role: "agent",
            text: result.suggestions.length
              ? `Saved the report and drafted ${result.suggestions.length} value${result.suggestions.length === 1 ? "" : "s"}. Approve the ones you want on the chart.`
              : "Stored the uploaded document. No values were extracted or added to the recorded results.",
            route: "chart",
            routedBy: "auto",
          };
          const actions = result.suggestions.map((row) => suggestionAction(row, { conversationId, messageId: message.id }));
          updateConversation(conversationId, (c) => ({ ...c, messages: [...c.messages, message] }));
          set((s) => ({
            actions: [...s.actions, ...actions],
            activeConversationId: conversationId,
            layout: s.layout === "workspace" ? "split" : s.layout,
            notice: null,
          }));
          try { await refreshPatient(patientId); } catch { set({ notice: "Document stored, but the chart could not refresh. Reload before uploading again." }); }
          return result;
        } catch (error) {
          set({ notice: explain(error, "The document upload could not be confirmed. Check before retrying.") });
        }
    },

    runReminders: (patientId) => {
      void (async () => {
        try {
          const result = await runReminderJob(todayIso());
          const sent = result.sent.length;
          const skipped = result.skipped.length;
          set((s) => ({
            sms: {
              ...s.sms,
              [patientId]: sent
                ? `Sent ${sent} reminder${sent === 1 ? "" : "s"}. ${skipped} skipped. Messages do not include health details.`
                : skipped
                  ? `Nothing new was sent. ${skipped} reminder${skipped === 1 ? " was" : "s were"} skipped.`
                  : "No reminders were due.",
            },
            notice: null,
          }));
          audit(patientId, "SMS", `${sent} reminder(s) sent.`);
          await refreshPatient(patientId);
        } catch (error) {
          set((s) => ({
            sms: { ...s.sms, [patientId]: explain(error, "Reminders were not sent. The messaging service did not accept the send.") },
          }));
        }
      })();
    },

    optOut: (patientId) => {
      const patient = get().patients[patientId];
      if (!patient?.phone || !patient.smsOptIn) return;
      void (async () => {
        try {
          await sendStop(patient.phone!);
          await refreshPatient(patientId);
          set((s) => ({
            sms: { ...s.sms, [patientId]: "STOP received. SMS is off for this patient." },
            notice: null,
          }));
          audit(patientId, "Opt-out", "Patient replied STOP.");
        } catch (error) {
          set({ notice: explain(error, "The opt-out did not reach the clinic API.") });
        }
      })();
    },
  };
});
