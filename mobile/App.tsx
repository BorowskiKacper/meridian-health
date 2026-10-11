import { StatusBar } from "expo-status-bar";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError, apiBaseUrl, createClient, type AudioPart, type DoctorInput } from "./src/api";
import { CitationList } from "./src/components/CitationList";
import { SuggestionCard } from "./src/components/SuggestionCard";
import { reviewSummary, routeLabel } from "./src/format";
import { DEMO_PATIENTS } from "./src/patients";
import { playReadBack } from "./src/playback";
import type { DoctorRequest, Suggestion } from "./src/types";

type UserMessage = { id: string; role: "user"; channel: "typed" | "voice"; text: string };
type AgentMessage = { id: string; role: "agent"; response: DoctorRequest };
type NoteMessage = { id: string; role: "note"; text: string };
type ThreadMessage = UserMessage | AgentMessage | NoteMessage;

let messageCount = 0;

function nextId(): string {
  messageCount += 1;
  return `m${messageCount}`;
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Could not reach the API.";
}

export default function App() {
  const visit = useMemo(() => createClient(apiBaseUrl()), []);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const scrollRef = useRef<ScrollView>(null);
  const recordingPatient = useRef<string>(DEMO_PATIENTS[0].id);
  const [patientId, setPatientId] = useState<string>(DEMO_PATIENTS[0].id);
  const [threads, setThreads] = useState<Record<string, ThreadMessage[]>>({});
  const [pending, setPending] = useState<Record<string, Suggestion[]>>({});
  const [handled, setHandled] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [loadingQueue, setLoadingQueue] = useState(false);

  const patient = DEMO_PATIENTS.find((item) => item.id === patientId) ?? DEMO_PATIENTS[0];
  const thread = threads[patientId] ?? [];
  const queue = (pending[patientId] ?? []).map((suggestion) => withStatus(suggestion, handled));

  useEffect(() => {
    let active = true;
    setLoadingQueue(true);
    setQueueError(null);
    visit
      .listPending(patientId)
      .then((suggestions) => {
        if (!active) return;
        setPending((current) => ({ ...current, [patientId]: suggestions }));
      })
      .catch((error: unknown) => {
        if (!active) return;
        setQueueError(messageOf(error));
      })
      .finally(() => {
        if (active) setLoadingQueue(false);
      });
    return () => {
      active = false;
    };
  }, [patientId, visit]);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [thread.length, queue.length]);

  function append(forPatient: string, message: ThreadMessage) {
    setThreads((current) => ({
      ...current,
      [forPatient]: [...(current[forPatient] ?? []), message],
    }));
  }

  function replaceUserText(forPatient: string, id: string, text: string) {
    setThreads((current) => ({
      ...current,
      [forPatient]: (current[forPatient] ?? []).map((message) =>
        message.role === "user" && message.id === id ? { ...message, text } : message,
      ),
    }));
  }

  async function refresh(forPatient: string) {
    const suggestions = await visit.listPending(forPatient);
    setPending((current) => ({ ...current, [forPatient]: suggestions }));
    setQueueError(null);
  }

  async function submit(forPatient: string, input: DoctorInput, userText: string) {
    const userId = nextId();
    const channel = "audio" in input ? "voice" : "typed";
    append(forPatient, { id: userId, role: "user", channel, text: userText });
    setBusy(true);
    try {
      const response = await visit.sendRequest(forPatient, input);
      if (channel === "voice" && response.transcript.trim()) {
        replaceUserText(forPatient, userId, response.transcript);
      }
      append(forPatient, { id: nextId(), role: "agent", response });
      if (response.audio_base64) {
        try {
          playReadBack(response.audio_base64);
        } catch {
          // The read-back text is still on screen when playback is blocked.
        }
      }
    } catch (error) {
      append(forPatient, { id: nextId(), role: "note", text: messageOf(error) });
      setBusy(false);
      return;
    }
    try {
      await refresh(forPatient);
    } catch (error) {
      setQueueError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  async function sendTyped() {
    const text = draft.trim();
    if (!text || busy || recording) return;
    setDraft("");
    await submit(patientId, { text }, text);
  }

  async function startDictation() {
    if (busy || recording) return;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        append(patientId, {
          id: nextId(),
          role: "note",
          text: "Microphone permission is required to dictate.",
        });
        return;
      }
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      recordingPatient.current = patientId;
      setRecording(true);
    } catch {
      setRecording(false);
      append(patientId, { id: nextId(), role: "note", text: "The microphone could not start." });
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
    const forPatient = recordingPatient.current;
    setRecording(false);
    try {
      await recorder.stop();
    } catch {
      append(forPatient, { id: nextId(), role: "note", text: "The recording could not be stopped." });
      return;
    }
    const uri = recorder.uri;
    if (!uri) {
      append(forPatient, { id: nextId(), role: "note", text: "No audio was captured." });
      return;
    }
    const audio = await audioPartFromUri(uri);
    if (!audio) {
      append(forPatient, { id: nextId(), role: "note", text: "No audio was captured." });
      return;
    }
    await submit(forPatient, { audio }, "Dictation");
  }

  async function approve(id: string) {
    const forPatient = patientId;
    setBusyId(id);
    try {
      const result = await visit.approve([id]);
      setHandled((current) => ({ ...current, [id]: "approved" }));
      const summary = reviewSummary(
        result.reminder_review.answer,
        result.reminder_review.suggestions.length,
      );
      if (summary) append(forPatient, { id: nextId(), role: "note", text: summary });
    } catch (error) {
      append(forPatient, { id: nextId(), role: "note", text: messageOf(error) });
      setBusyId(null);
      return;
    }
    try {
      await refresh(forPatient);
    } catch (error) {
      setQueueError(messageOf(error));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id: string, reason: string) {
    const forPatient = patientId;
    setBusyId(id);
    try {
      await visit.reject([id], reason);
      setHandled((current) => ({ ...current, [id]: "rejected" }));
      append(forPatient, { id: nextId(), role: "note", text: "Suggestion rejected." });
    } catch (error) {
      append(forPatient, { id: nextId(), role: "note", text: messageOf(error) });
      setBusyId(null);
      return;
    }
    try {
      await refresh(forPatient);
    } catch (error) {
      setQueueError(messageOf(error));
    } finally {
      setBusyId(null);
    }
  }

  async function addToPlan(response: DoctorRequest) {
    const text = response.answer?.text.trim() ?? "";
    if (!text) return;
    const forPatient = patientId;
    setBusy(true);
    try {
      await visit.addToPlan(forPatient, response.request_id, text, response.answer?.citations ?? []);
      append(forPatient, { id: nextId(), role: "note", text: "Added to the plan as a suggestion." });
    } catch (error) {
      append(forPatient, { id: nextId(), role: "note", text: messageOf(error) });
      setBusy(false);
      return;
    }
    try {
      await refresh(forPatient);
    } catch (error) {
      setQueueError(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.frame}
      >
        <View style={styles.header}>
          <Text style={styles.kicker}>Doctor</Text>
          <Text style={styles.title}>Visit</Text>
          <Text style={styles.subtitle}>Type or dictate. One request goes to the agents.</Text>
        </View>
        <View style={styles.patients}>
          {DEMO_PATIENTS.map((item) => {
            const selected = item.id === patient.id;
            return (
              <Pressable
                accessibilityLabel={item.displayName}
                accessibilityState={{ selected }}
                disabled={recording}
                key={item.id}
                onPress={() => setPatientId(item.id)}
                style={[styles.chip, selected && styles.chipSelected]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
                  {item.displayName}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <ScrollView
          contentContainerStyle={styles.thread}
          ref={scrollRef}
          style={styles.scroll}
        >
          {loadingQueue ? <Text style={styles.meta}>Loading suggestions…</Text> : null}
          {queueError ? <Text style={styles.error}>{queueError}</Text> : null}
          {queue.length > 0 ? (
            <View style={styles.queue}>
              <Text style={styles.section}>Waiting for approval</Text>
              {queue.map((suggestion) => (
                <SuggestionCard
                  busy={busyId === suggestion.id}
                  key={suggestion.id}
                  onApprove={(id) => {
                    void approve(id);
                  }}
                  onReject={(id, reason) => {
                    void reject(id, reason);
                  }}
                  suggestion={suggestion}
                />
              ))}
            </View>
          ) : null}
          {thread.length === 0 ? (
            <Text style={styles.empty}>
              Ask a clinical question, check screenings, or update the chart. Chart changes stay
              suggestions until you approve them.
            </Text>
          ) : (
            thread.map((message) => (
              <ThreadBubble
                busy={busy || busyId !== null}
                key={message.id}
                message={message}
                onAddToPlan={(response) => {
                  void addToPlan(response);
                }}
                onApprove={(id) => {
                  void approve(id);
                }}
                onReject={(id, reason) => {
                  void reject(id, reason);
                }}
                statusFor={(id) => handled[id]}
              />
            ))
          )}
        </ScrollView>
        <View style={styles.composer}>
          {recording ? (
            <View style={styles.recordingRow}>
              <Text style={styles.recordingLabel}>Recording</Text>
              <Pressable accessibilityLabel="Cancel dictation" onPress={() => void cancelDictation()} style={styles.secondary}>
                <Text style={styles.secondaryText}>Cancel</Text>
              </Pressable>
              <Pressable accessibilityLabel="Send dictation" onPress={() => void sendDictation()} style={styles.primary}>
                <Text style={styles.primaryText}>Send</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.composeRow}>
              <TextInput
                accessibilityLabel="Message"
                editable={!busy}
                multiline
                onChangeText={setDraft}
                placeholder="Ask a question or update the chart"
                placeholderTextColor="#8a8178"
                style={styles.input}
                value={draft}
              />
              <Pressable
                accessibilityLabel="Send"
                disabled={busy || !draft.trim()}
                onPress={() => void sendTyped()}
                style={[styles.primary, (busy || !draft.trim()) && styles.disabled]}
              >
                <Text style={styles.primaryText}>{busy ? "Sending" : "Send"}</Text>
              </Pressable>
              <Pressable
                accessibilityLabel="Dictate"
                disabled={busy}
                onPress={() => void startDictation()}
                style={[styles.dictate, busy && styles.disabled]}
              >
                <Text style={styles.dictateText}>Dictate</Text>
              </Pressable>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

function withStatus(suggestion: Suggestion, handled: Record<string, string>): Suggestion {
  const status = handled[suggestion.id];
  if (!status) return suggestion;
  return { ...suggestion, status };
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

function ThreadBubble({
  message,
  busy,
  statusFor,
  onApprove,
  onReject,
  onAddToPlan,
}: {
  message: ThreadMessage;
  busy: boolean;
  statusFor: (id: string) => string | undefined;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  onAddToPlan: (response: DoctorRequest) => void;
}) {
  if (message.role === "note") {
    return <Text style={styles.note}>{message.text}</Text>;
  }
  if (message.role === "user") {
    return (
      <View style={styles.userWrap}>
        <Text style={styles.channel}>{message.channel === "voice" ? "Dictated" : "Typed"}</Text>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{message.text}</Text>
        </View>
      </View>
    );
  }
  const { response } = message;
  const suggestions = response.suggestions.map((suggestion) =>
    withStatus(suggestion, statusMap(statusFor, response.suggestions)),
  );
  return (
    <View style={styles.agentBubble}>
      <Text style={styles.route}>{routeLabel(response.route)}</Text>
      {response.spoken_text ? <Text style={styles.spoken}>{response.spoken_text}</Text> : null}
      {response.audio_base64 ? (
        <Pressable
          accessibilityLabel="Play read-back"
          onPress={() => playReadBack(response.audio_base64 as string)}
          style={styles.play}
        >
          <Text style={styles.playText}>Play read-back</Text>
        </Pressable>
      ) : null}
      {response.answer?.text ? <Text style={styles.answer}>{response.answer.text}</Text> : null}
      <CitationList citations={response.answer?.citations ?? []} />
      {response.answer?.text ? (
        <Pressable
          accessibilityLabel="Add to plan"
          disabled={busy}
          onPress={() => onAddToPlan(response)}
          style={[styles.secondary, busy && styles.disabled]}
        >
          <Text style={styles.secondaryText}>Add to plan</Text>
        </Pressable>
      ) : null}
      {suggestions.map((suggestion) => (
        <SuggestionCard
          busy={busy}
          key={suggestion.id}
          onApprove={onApprove}
          onReject={onReject}
          suggestion={suggestion}
        />
      ))}
    </View>
  );
}

function statusMap(statusFor: (id: string) => string | undefined, suggestions: Suggestion[]): Record<string, string> {
  const handled: Record<string, string> = {};
  for (const suggestion of suggestions) {
    const status = statusFor(suggestion.id);
    if (status) handled[suggestion.id] = status;
  }
  return handled;
}

const styles = StyleSheet.create({
  screen: { backgroundColor: "#e7e0d6", flex: 1 },
  frame: {
    alignSelf: "center",
    backgroundColor: "#f7f4ef",
    flex: 1,
    maxWidth: 480,
    width: "100%",
  },
  header: { paddingBottom: 8, paddingHorizontal: 20, paddingTop: 18 },
  kicker: {
    color: "#1f6f5b",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  title: { color: "#1f1a17", fontSize: 32, fontWeight: "700", marginTop: 2 },
  subtitle: { color: "#6d645c", fontSize: 14, marginTop: 4 },
  patients: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingHorizontal: 20, paddingVertical: 8 },
  chip: {
    backgroundColor: "#fffdf9",
    borderColor: "#e4d9cc",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  chipSelected: { backgroundColor: "#1f6f5b", borderColor: "#1f6f5b" },
  chipText: { color: "#1f1a17", fontSize: 14, fontWeight: "600" },
  chipTextSelected: { color: "#f4fbf8" },
  scroll: { flex: 1 },
  thread: { gap: 12, paddingBottom: 16, paddingHorizontal: 20, paddingTop: 8 },
  section: { color: "#6d645c", fontSize: 12, fontWeight: "700", letterSpacing: 0.4, textTransform: "uppercase" },
  queue: { gap: 8 },
  empty: { color: "#6d645c", fontSize: 16, lineHeight: 23, marginTop: 12 },
  meta: { color: "#6d645c", fontSize: 13 },
  error: { color: "#8c3a32", fontSize: 14, lineHeight: 20 },
  note: { color: "#6d645c", fontSize: 14, lineHeight: 20 },
  userWrap: { alignItems: "flex-end", gap: 4 },
  channel: { color: "#8a8178", fontSize: 11, fontWeight: "600" },
  userBubble: {
    backgroundColor: "#1f6f5b",
    borderRadius: 16,
    maxWidth: "88%",
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  userText: { color: "#f4fbf8", fontSize: 16, lineHeight: 22 },
  agentBubble: {
    backgroundColor: "#fffdf9",
    borderColor: "#e4d9cc",
    borderRadius: 16,
    borderWidth: 1,
    gap: 8,
    padding: 14,
  },
  route: { color: "#1f6f5b", fontSize: 12, fontWeight: "700", letterSpacing: 0.4, textTransform: "uppercase" },
  spoken: { color: "#1f1a17", fontSize: 16, lineHeight: 22 },
  answer: { color: "#1f1a17", fontSize: 16, lineHeight: 23 },
  play: { alignSelf: "flex-start" },
  playText: { color: "#1f6f5b", fontSize: 14, fontWeight: "700" },
  composer: {
    borderTopColor: "#e4d9cc",
    borderTopWidth: 1,
    paddingBottom: 16,
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  composeRow: { alignItems: "flex-end", flexDirection: "row", gap: 8 },
  recordingRow: { alignItems: "center", flexDirection: "row", gap: 8 },
  recordingLabel: { color: "#8c3a32", flex: 1, fontSize: 16, fontWeight: "700" },
  input: {
    backgroundColor: "#fffdf9",
    borderColor: "#e4d9cc",
    borderRadius: 14,
    borderWidth: 1,
    color: "#1f1a17",
    flex: 1,
    fontSize: 16,
    maxHeight: 120,
    minHeight: 44,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  primary: {
    backgroundColor: "#1f6f5b",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  primaryText: { color: "#f4fbf8", fontSize: 15, fontWeight: "700" },
  dictate: {
    backgroundColor: "#8c3a32",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  dictateText: { color: "#fff7f5", fontSize: 15, fontWeight: "700" },
  secondary: {
    borderColor: "#1f6f5b",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  secondaryText: { color: "#1f6f5b", fontSize: 14, fontWeight: "700" },
  disabled: { opacity: 0.45 },
});
