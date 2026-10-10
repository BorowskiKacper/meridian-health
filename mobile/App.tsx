import { StatusBar } from "expo-status-bar";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import { useMemo, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError, apiBaseUrl, createClient, type AudioPart, type DoctorInput } from "./src/api";
import {
  patientMrn,
  replyText,
  chatRoute,
  type AgentTurn,
  type ChatConversation,
  type ChatMode,
  type DoctorTurn,
} from "./src/chat";
import { Composer } from "./src/components/composer";
import { Conversation } from "./src/components/conversation";
import { playReadBack } from "./src/playback";
import { DEMO_PATIENTS } from "./src/patients";
import { theme } from "./src/theme";

let sequence = 0;

function nextId(): string {
  sequence += 1;
  return `m${sequence}`;
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The clinic API could not classify this request. The chart model is not configured, so nothing was saved.";
}

function openConversation(patientId: string, title: string): ChatConversation {
  return { id: nextId(), patientId, title, messages: [] };
}

export default function App() {
  const client = useMemo(() => createClient(apiBaseUrl()), []);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recordingConversation = useRef<string>("");
  const jane = DEMO_PATIENTS[0];
  const [conversations, setConversations] = useState<ChatConversation[]>(() => [
    openConversation(jane.id, jane.displayName),
  ]);
  const [activeId, setActiveId] = useState<string>(() => "");
  const [mode, setMode] = useState<ChatMode>("auto");
  const [draft, setDraft] = useState("");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const resolvedActiveId = activeId || conversations[0]?.id || "";
  const active = conversations.find((conversation) => conversation.id === resolvedActiveId) ?? null;
  const patient = DEMO_PATIENTS.find((item) => item.id === active?.patientId) ?? jane;

  function updateConversation(id: string, mapper: (conversation: ChatConversation) => ChatConversation) {
    setConversations((current) =>
      current.map((conversation) => (conversation.id === id ? mapper(conversation) : conversation)),
    );
  }

  function patchTurn(conversationId: string, turnId: string, patch: Partial<AgentTurn> | Partial<DoctorTurn>) {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((turn) =>
        turn.id === turnId ? ({ ...turn, ...patch } as typeof turn) : turn,
      ),
    }));
  }

  function say(conversationId: string, text: string) {
    const turn: AgentTurn = {
      id: nextId(),
      role: "agent",
      text,
      pending: false,
      suggestions: [],
      answer: null,
      audioBase64: null,
    };
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: [...conversation.messages, turn],
    }));
  }

  async function submit(conversationId: string, patientId: string, input: DoctorInput, userText: string) {
    const doctorId = nextId();
    const agentId = nextId();
    const doctor: DoctorTurn = { id: doctorId, role: "doctor", text: userText };
    const agent: AgentTurn = {
      id: agentId,
      role: "agent",
      text: "",
      pending: true,
      suggestions: [],
      answer: null,
      audioBase64: null,
    };
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: [...conversation.messages, doctor, agent],
    }));
    setBusy(true);
    try {
      const response = await client.sendRequest(patientId, input);
      if ("audio" in input && response.transcript.trim()) {
        patchTurn(conversationId, doctorId, { text: response.transcript });
      }
      const route = chatRoute(response.route) ?? undefined;
      patchTurn(conversationId, agentId, {
        text: replyText(response),
        pending: false,
        route,
        suggestions: response.suggestions,
        answer: response.answer,
        audioBase64: response.audio_base64,
      });
      if (response.audio_base64) {
        try {
          playReadBack(response.audio_base64);
        } catch {
          // The reply stays on screen when playback is blocked.
        }
      }
    } catch (error) {
      patchTurn(conversationId, agentId, { text: messageOf(error), pending: false });
    } finally {
      setBusy(false);
    }
  }

  function sendText(text: string) {
    const value = text.trim();
    if (!value || !active || busy || recording) return;
    setDraft("");
    void submit(active.id, active.patientId, { text: value }, value);
  }

  async function startDictation() {
    if (!active || busy || recording) return;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        say(active.id, "Microphone permission is required to dictate.");
        return;
      }
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      recordingConversation.current = active.id;
      setRecording(true);
    } catch {
      setRecording(false);
      say(active.id, "The microphone could not start.");
    }
  }

  async function cancelDictation() {
    try {
      await recorder.stop();
    } catch {
      // Stopping an idle recorder is safe to ignore.
    }
    setRecording(false);
  }

  async function sendDictation() {
    const conversationId = recordingConversation.current;
    const conversation = conversations.find((item) => item.id === conversationId);
    setRecording(false);
    try {
      await recorder.stop();
    } catch {
      if (conversation) say(conversation.id, "The recording could not be stopped.");
      return;
    }
    if (!conversation) return;
    const uri = recorder.uri;
    if (!uri) {
      say(conversation.id, "No audio was captured.");
      return;
    }
    const audio = await audioPartFromUri(uri);
    if (!audio) {
      say(conversation.id, "No audio was captured.");
      return;
    }
    await submit(conversation.id, conversation.patientId, { audio }, "Dictating…");
  }

  function dictate() {
    if (recording) {
      void sendDictation();
      return;
    }
    void startDictation();
  }

  async function approve(messageId: string, suggestionId: string) {
    if (!active) return;
    const conversationId = active.id;
    setBusyId(suggestionId);
    try {
      const result = await client.approve([suggestionId]);
      markSuggestion(conversationId, messageId, suggestionId, "approved");
      const review = result.reminder_review.answer?.trim();
      if (review) {
        const turn: AgentTurn = {
          id: nextId(),
          role: "agent",
          text: review,
          pending: false,
          route: "screening",
          suggestions: [],
          answer: null,
          audioBase64: null,
        };
        updateConversation(conversationId, (conversation) => ({
          ...conversation,
          messages: [...conversation.messages, turn],
        }));
      }
    } catch (error) {
      say(conversationId, messageOf(error));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(messageId: string, suggestionId: string) {
    if (!active) return;
    const conversationId = active.id;
    setBusyId(suggestionId);
    try {
      await client.reject([suggestionId], "Not accurate");
      markSuggestion(conversationId, messageId, suggestionId, "rejected");
    } catch (error) {
      say(conversationId, messageOf(error));
    } finally {
      setBusyId(null);
    }
  }

  function markSuggestion(conversationId: string, messageId: string, suggestionId: string, status: string) {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((turn) => {
        if (turn.id !== messageId || turn.role !== "agent") return turn;
        return {
          ...turn,
          suggestions: turn.suggestions.map((suggestion) =>
            suggestion.id === suggestionId ? { ...suggestion, status } : suggestion,
          ),
        };
      }),
    }));
  }

  function newConversation(patientId: string) {
    const match = DEMO_PATIENTS.find((item) => item.id === patientId);
    if (!match || recording) return;
    const conversation = openConversation(match.id, match.displayName);
    setConversations((current) => [...current, conversation]);
    setActiveId(conversation.id);
    setMenuOpen(false);
    setDraft("");
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.frame}>
        <View style={styles.window}>
          <View style={styles.header}>
            <View accessibilityRole="tablist" style={styles.tabs}>
              {conversations.map((conversation) => {
                const selected = conversation.id === resolvedActiveId;
                return (
                  <Pressable
                    accessibilityLabel={conversation.title}
                    accessibilityRole="tab"
                    accessibilityState={{ selected }}
                    disabled={recording}
                    key={conversation.id}
                    onPress={() => setActiveId(conversation.id)}
                    style={[styles.tab, selected && styles.tabOn]}
                  >
                    <Text style={[styles.tabText, selected ? styles.tabTextOn : styles.tabTextOff]}>
                      {conversation.title}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            <Pressable
              accessibilityLabel="New conversation"
              disabled={recording}
              onPress={() => setMenuOpen((open) => !open)}
              style={styles.plus}
            >
              <Text style={styles.plusText}>+</Text>
            </Pressable>
          </View>

          {active ? (
            <View style={styles.column}>
              <View style={styles.identity}>
                <Text style={styles.assistant}>Assistant</Text>
                <Text style={styles.who}>
                  {patient.displayName} · {patientMrn(patient.id)}
                </Text>
              </View>
              <Conversation
                busyId={busyId}
                conversation={active}
                onApprove={(messageId, suggestionId) => {
                  void approve(messageId, suggestionId);
                }}
                onPlay={playReadBack}
                onReject={(messageId, suggestionId) => {
                  void reject(messageId, suggestionId);
                }}
                onStarter={sendText}
                patientName={patient.displayName}
              />
              <Composer
                busy={busy}
                listening={recording}
                mode={mode}
                onCancelDictation={() => {
                  void cancelDictation();
                }}
                onDictate={dictate}
                onMode={setMode}
                onSend={() => sendText(draft)}
                onText={setDraft}
                patientName={patient.displayName}
                text={draft}
              />
            </View>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>Start a conversation with the plus button.</Text>
            </View>
          )}

          {menuOpen ? (
            <>
              <Pressable accessibilityLabel="Close menu" onPress={() => setMenuOpen(false)} style={styles.scrim} />
              <View style={styles.menu}>
                <Text style={styles.menuLabel}>New conversation about</Text>
                {DEMO_PATIENTS.map((item) => (
                  <Pressable key={item.id} onPress={() => newConversation(item.id)} style={styles.menuItem}>
                    <Text style={styles.menuName}>{item.displayName}</Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

async function audioPartFromUri(uri: string): Promise<AudioPart | null> {
  if (uri.startsWith("blob:") || uri.startsWith("data:") || uri.startsWith("http")) {
    const response = await fetch(uri);
    const blob = await response.blob();
    if (blob.size === 0) return null;
    return blob;
  }
  const webm = uri.toLowerCase().includes(".webm");
  return {
    uri,
    name: webm ? "dictation.webm" : "dictation.m4a",
    type: webm ? "audio/webm" : "audio/mp4",
  };
}

const styles = StyleSheet.create({
  screen: { backgroundColor: theme.jade900, flex: 1 },
  frame: { flex: 1 },
  window: { alignSelf: "center", flex: 1, maxWidth: 768, width: "100%" },
  header: {
    alignItems: "flex-end",
    borderBottomColor: theme.ivory15,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: 4,
    paddingHorizontal: 12,
    paddingTop: Platform.OS === "ios" ? 52 : 10,
  },
  tabs: { flex: 1, flexDirection: "row", gap: 4 },
  tab: { borderBottomColor: "transparent", borderBottomWidth: 2, height: 36, justifyContent: "center", paddingHorizontal: 8 },
  tabOn: { borderBottomColor: theme.jade300 },
  tabText: { fontSize: 12 },
  tabTextOn: { color: theme.ivory },
  tabTextOff: { color: theme.ivory45 },
  plus: { alignItems: "center", height: 28, justifyContent: "center", marginBottom: 6, width: 28 },
  plusText: { color: theme.ivory45, fontSize: 22, lineHeight: 24 },
  column: { flex: 1, paddingHorizontal: 24 },
  identity: {
    alignItems: "center",
    borderBottomColor: theme.ivory14,
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 16,
  },
  assistant: { color: theme.jade300, fontSize: 12, fontWeight: "600" },
  who: { color: theme.ivory65, fontSize: 12 },
  empty: { alignItems: "center", flex: 1, justifyContent: "center", paddingHorizontal: 32 },
  emptyText: { color: theme.ivory65, fontSize: 14, textAlign: "center" },
  scrim: { ...StyleSheet.absoluteFill },
  menu: {
    backgroundColor: theme.white,
    borderRadius: 8,
    paddingVertical: 8,
    position: "absolute",
    right: 12,
    top: 52,
    width: 220,
    zIndex: 2,
  },
  menuLabel: { color: theme.inkFaint, fontSize: 12, paddingHorizontal: 12, paddingVertical: 6 },
  menuItem: { paddingHorizontal: 12, paddingVertical: 10 },
  menuName: { color: theme.ink, fontSize: 14 },
});
