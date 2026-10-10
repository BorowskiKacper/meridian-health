import { StatusBar } from "expo-status-bar";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import { useMemo, useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, View } from "react-native";

import { ApiError, apiBaseUrl, createClient, type AudioPart, type DoctorInput } from "./src/api";
import { chatRoute, phoneReply, type AgentTurn, type ChatMode, type DoctorTurn, type Turn } from "./src/chat";
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

export default function App() {
  const client = useMemo(() => createClient(apiBaseUrl()), []);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  // The request contract requires a patient id. The phone does not choose one.
  const patientId = DEMO_PATIENTS[0].id;
  const [messages, setMessages] = useState<Turn[]>([]);
  const [mode, setMode] = useState<ChatMode>("auto");
  const [draft, setDraft] = useState("");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);

  function patchTurn(turnId: string, patch: Partial<AgentTurn> | Partial<DoctorTurn>) {
    setMessages((current) =>
      current.map((turn) => (turn.id === turnId ? ({ ...turn, ...patch } as typeof turn) : turn)),
    );
  }

  function say(text: string) {
    const turn: AgentTurn = {
      id: nextId(),
      role: "agent",
      text,
      pending: false,
      suggestions: [],
      answer: null,
      audioBase64: null,
    };
    setMessages((current) => [...current, turn]);
  }

  async function submit(input: DoctorInput, userText: string) {
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
    setMessages((current) => [...current, doctor, agent]);
    setBusy(true);
    try {
      const response = await client.sendRequest(patientId, input);
      if ("audio" in input && response.transcript.trim()) {
        patchTurn(doctorId, { text: response.transcript });
      }
      const reply = phoneReply(response);
      const route = chatRoute(response.route) ?? undefined;
      patchTurn(agentId, {
        text: reply.text,
        pending: false,
        route,
        answer: reply.answer,
        audioBase64: reply.answer ? response.audio_base64 : null,
      });
      if (reply.answer && response.audio_base64) {
        try {
          playReadBack(response.audio_base64);
        } catch {
          // The reply stays on screen when playback is blocked.
        }
      }
    } catch (error) {
      patchTurn(agentId, { text: messageOf(error), pending: false });
    } finally {
      setBusy(false);
    }
  }

  function sendText(text: string) {
    const value = text.trim();
    if (!value || busy || recording) return;
    setDraft("");
    void submit({ text: value }, value);
  }

  async function startDictation() {
    if (busy || recording) return;
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        say("Microphone permission is required to dictate.");
        return;
      }
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setRecording(true);
    } catch {
      setRecording(false);
      say("The microphone could not start.");
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
    setRecording(false);
    try {
      await recorder.stop();
    } catch {
      say("The recording could not be stopped.");
      return;
    }
    const uri = recorder.uri;
    if (!uri) {
      say("No audio was captured.");
      return;
    }
    const audio = await audioPartFromUri(uri);
    if (!audio) {
      say("No audio was captured.");
      return;
    }
    await submit({ audio }, "Dictating…");
  }

  function dictate() {
    if (recording) {
      void sendDictation();
      return;
    }
    void startDictation();
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.frame}>
        <View style={styles.window}>
          <View style={styles.header}>
            <Text style={styles.assistant}>Assistant</Text>
          </View>
          <View style={styles.column}>
            <Conversation
              messages={messages}
              onPlay={playReadBack}
              onStarter={sendText}
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
              text={draft}
            />
          </View>
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
    borderBottomColor: theme.ivory15,
    borderBottomWidth: 1,
    paddingBottom: 12,
    paddingHorizontal: 24,
    paddingTop: Platform.OS === "ios" ? 52 : 16,
  },
  assistant: { color: theme.jade300, fontSize: 12, fontWeight: "600" },
  column: { flex: 1, paddingHorizontal: 24 },
});
