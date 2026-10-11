import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import * as Crypto from 'expo-crypto';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AppState, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ApiError, apiBaseUrl, type AudioPart } from '../api';
import { loadDevice, saveDevice } from '../device';
import { workspaceClient, type WorkspaceJob } from '../workspace-api';
import { deliveryStatus } from '../workspace-status';
import { CitationList } from '../components/CitationList';
import { SuggestionCard } from '../components/SuggestionCard';
import { DictationButton } from '../components/DictationButton';

export default function Companion() {
  const client = useMemo(() => workspaceClient(apiBaseUrl()), []);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [code, setCode] = useState('');
  const [jobs, setJobs] = useState<WorkspaceJob[]>([]);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [retryRecording, setRetryRecording] = useState(false);
  const [connected, setConnected] = useState(false);
  const [listeningPatient, setListeningPatient] = useState<string | null>(null);
  const [patient, setPatient] = useState<string | null>(null);
  const [patientId, setPatientId] = useState<string | null>(null);
  const lastPhoneJob = useRef<string | null>(null);
  const recordingContext = useRef<string | null>(null);
  const pendingSubmission = useRef<{ id: string; text?: string; audio?: AudioPart; patientId: string | null } | null>(null);
  const retryAudio = useRef<AudioPart | undefined>(undefined);
  const scroll = useRef<ScrollView>(null);
  const [clarifyingJobId, setClarifyingJobId] = useState<string | null>(null);
  const updates = useRef(0);
  const waiting = jobs.find((job) => job.id === clarifyingJobId && job.status === 'needs_patient');

  useEffect(() => { void loadDevice().then(setToken).catch(() => setError('Saved pairing could not load. Please pair again.')).finally(() => setLoading(false)); }, []);
  useEffect(() => {
    if (!token) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let polling = false;
    const refresh = async () => {
      if (polling || stopped) return;
      polling = true;
      const version = updates.current;
      try {
        const state = await client.state(token);
        if (!stopped) {
          setConnected(true);
          if (version === updates.current) {
            setJobs(state.jobs);
            const own = state.jobs.find((j) => j.id === lastPhoneJob.current);
            if (own && (own.status === 'completed' || own.status === 'needs_patient')) {
              setPatient(own.patient_name); setPatientId(own.patient_id);
            }
          }
        }
      } catch (e) {
        if (!stopped) setConnected(false);
        if (e instanceof ApiError && e.status === 401 && !stopped) {
          await saveDevice(null); setToken(null); setJobs([]); setPatient(null); setPatientId(null); lastPhoneJob.current = null; pendingSubmission.current = null; retryAudio.current = undefined; setRetryRecording(false); setError('This phone was disconnected. Pair again to continue.');
        }
      } finally { polling = false; if (!stopped) timer = setTimeout(() => void refresh(), AppState.currentState !== 'background' ? 1000 : 10000); }
    };
    const foreground = AppState.addEventListener('change', (state) => { if (state === 'active') { clearTimeout(timer); void refresh(); } });
    void refresh();
    return () => { stopped = true; clearTimeout(timer); foreground.remove(); };
  }, [client, token]);
  useEffect(() => { scroll.current?.scrollToEnd({ animated: true }); }, [jobs.length, waiting?.id]);

  const replaceJob = (job: WorkspaceJob) => {
    updates.current += 1;
    lastPhoneJob.current = job.id;
    if (job.patient_name) { setPatient(job.patient_name); setPatientId(job.patient_id); }
    setJobs((all) => [...all.filter((j) => j.id !== job.id), job]);
  };
  const report = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Not confirmed as sent. Check your connection and retry the same prompt.');
  const send = async (audio?: AudioPart) => {
    if (!token || busy || (!audio && !text.trim())) return;
    setBusy(true); setError(''); setRetryRecording(false);
    retryAudio.current = audio;
    try {
      if (waiting) {
        replaceJob(audio ? await client.clarifyVoice(token, waiting.id, audio) : await client.clarify(token, waiting.id, text));
        setClarifyingJobId(null);
      } else {
        const existing = pendingSubmission.current;
        const submission = existing && (audio ? existing.audio === audio : existing.text === text.trim()) ? existing : { id: Crypto.randomUUID(), text: audio ? undefined : text.trim(), audio, patientId: audio ? recordingContext.current : patientId };
        pendingSubmission.current = submission;
        replaceJob(await client.submit(token, submission.id, submission.text, submission.audio, submission.patientId));
        pendingSubmission.current = null;
      }
      setText('');
      retryAudio.current = undefined;
    } catch (e) { report(e); if (audio) setRetryRecording(true); }
    finally { setBusy(false); }
  };
  const record = async () => {
    if (busy) return;
    setError('');
    try {
      if (recording) {
        await recorder.stop(); setRecording(false);
        const uri = recorder.uri;
        if (!uri) throw new Error('No recording available.');
        const audio: AudioPart = Platform.OS === 'web' ? await (await fetch(uri)).blob() : { uri, name: 'dictation.m4a', type: 'audio/mp4' };
        await send(audio);
      } else {
        const permission = await AudioModule.requestRecordingPermissionsAsync();
        if (!permission.granted) { setError('Microphone access is off. You can still type a prompt.'); return; }
        await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
        recordingContext.current = patientId;
        await recorder.prepareToRecordAsync(); recorder.record(); setRecording(true); setListeningPatient(patient ?? null);
      }
    } catch { setRecording(false); setError('The recording could not finish. Try again or type your prompt.'); }
  };
  const choose = async (job: WorkspaceJob, patientId?: string, query = '') => {
    if (!token || busy) return;
    setBusy(true); setError('');
    try { replaceJob(await client.clarify(token, job.id, query, patientId)); }
    catch (e) { report(e); } finally { setBusy(false); }
  };
  const review = async (id: string, approve: boolean, reason = '') => {
    if (!token || reviewing) return;
    setReviewing(id); setError('');
    try {
      if (approve) await client.approve(token, [id]); else await client.reject(token, [id], reason);
      const state = await client.state(token); setJobs(state.jobs);
    } catch (e) { report(e); } finally { setReviewing(null); }
  };

  if (loading) return <SafeAreaView style={styles.page}><Text style={styles.muted}>Loading your workspace…</Text></SafeAreaView>;
  if (!token) return <SafeAreaView style={styles.page}><KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.pair}>
    <Text style={styles.brand}>Meridian</Text><Text style={styles.heading}>Your workspace, wherever you are.</Text><Text style={styles.muted}>On your laptop, choose Connect phone. Enter its code here to pair once.</Text>
    <TextInput accessibilityLabel="Laptop pairing code" autoCapitalize="characters" autoCorrect={false} maxLength={12} placeholder="Pairing code" placeholderTextColor="#74877d" style={styles.code} value={code} onChangeText={setCode} />
    <Pressable disabled={busy || !code.trim()} style={[styles.primary, (busy || !code.trim()) && styles.disabled]} onPress={() => {
      setBusy(true); setError(''); void client.pair(code).then(async (device) => { await saveDevice(device.token); setToken(device.token); }).catch(report).finally(() => setBusy(false));
    }}><Text style={styles.primaryText}>{busy ? 'Connecting…' : 'Connect to laptop'}</Text></Pressable>
    <Text style={styles.small}>Your pairing stays active until you disconnect.</Text>{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
  </KeyboardAvoidingView></SafeAreaView>;

  return <SafeAreaView style={styles.page}><KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <View style={styles.header}><View><Text style={styles.brand}>Meridian</Text><Text style={styles.small}>{connected ? 'Paired with your laptop' : 'Reconnecting…'}</Text></View><Pressable accessibilityLabel="Disconnect phone" onPress={() => {
      if (busy || recording) return; setBusy(true); void client.disconnect(token).then(async () => { await saveDevice(null); setToken(null); setJobs([]); setPatient(null); setPatientId(null); lastPhoneJob.current = null; pendingSubmission.current = null; retryAudio.current = undefined; setRetryRecording(false); setText(''); }).catch(report).finally(() => setBusy(false));
    }}><Text style={styles.small}>Disconnect</Text></Pressable></View>
    <ScrollView ref={scroll} contentContainerStyle={styles.thread} keyboardShouldPersistTaps="handled">
      {!jobs.length && <View style={styles.empty}><Text style={styles.heading}>What would you like prepared?</Text><Text style={styles.muted}>Name a patient and ask a question, describe a chart change, or ask to open a view on your laptop.</Text></View>}
      {jobs.map((job) => <View key={job.id} style={styles.exchange}>
        <View style={styles.user}><Text style={styles.userText}>{job.text || 'Voice request'}</Text></View>
        <View style={styles.answer}>
          {job.patient_name && <Text style={styles.patient}>{job.patient_name}</Text>}
          {job.status === 'queued' || job.status === 'running' ? <Text accessibilityLiveRegion="polite" style={styles.muted}>{job.status === 'queued' ? 'Request received…' : 'Working on your request…'}</Text> : null}
          {job.question && job.status === 'needs_patient' && <><Text style={styles.answerText}>{job.question}</Text>{job.candidates?.map((p) => <Pressable key={p.id} disabled={busy} style={styles.choice} onPress={() => void choose(job, p.id)}><Text style={styles.answerText}>{p.display_name}</Text><Text style={styles.small}>DOB {p.date_of_birth}</Text></Pressable>)}<PatientClarification busy={busy || recording} onUse={(query) => void choose(job, undefined, query)} onVoice={() => setClarifyingJobId(job.id)} /></>}
          {job.error && <Text accessibilityRole="alert" style={styles.error}>{job.error}</Text>}
          {job.response?.answer && <AnswerText text={job.response.answer.text} />}
          {job.response?.answer?.citations.length ? <Evidence job={job} /> : null}
          {job.response?.suggestions.map((suggestion) => <SuggestionCard key={suggestion.id} suggestion={suggestion} busy={Boolean(reviewing)} onApprove={(id) => void review(id, true)} onReject={(id, reason) => void review(id, false, reason)} />)}
          {job.status === 'completed' && <Text accessibilityLiveRegion="polite" style={styles.small}>{deliveryStatus(job)}{job.response?.suggestions.length ? ' · Chart changes require approval' : ''}</Text>}
        </View>
      </View>)}
    </ScrollView>
    <View style={styles.composer}>
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {retryRecording && !busy && error ? <Pressable onPress={() => void send(retryAudio.current)}><Text style={styles.small}>Retry recording</Text></Pressable> : null}
      {waiting && <View style={{ gap: 4 }}><Text style={styles.small}>Answering patient question: {waiting.text || 'Voice request'}</Text><Pressable disabled={busy || recording} onPress={() => setClarifyingJobId(null)}><Text style={styles.evidence}>Start a new request instead</Text></Pressable></View>}
      {(recording ? listeningPatient : patient) && <Text style={styles.patient}>{recording ? listeningPatient : patient}</Text>}
      <DictationButton recording={recording} busy={busy} onPress={() => void record()} />
      <View style={styles.typedComposer}>
        <TextInput accessibilityLabel={waiting ? 'Patient name or record ID' : 'Clinical prompt'} multiline editable={!busy && !recording} style={styles.input} value={text} onChangeText={setText} placeholder={waiting ? 'Which patient?' : 'Or type a request…'} placeholderTextColor="#74877d" />
        <Pressable accessibilityRole="button" accessibilityLabel="Send typed request" disabled={busy || recording || !text.trim()} style={[styles.send, (busy || recording || !text.trim()) && styles.disabled]} onPress={() => void send()}><Text style={styles.sendText}>Send</Text></Pressable>
      </View>
    </View>
  </KeyboardAvoidingView></SafeAreaView>;
}

function PatientClarification({ busy, onUse, onVoice }: { busy: boolean; onUse: (query: string) => void; onVoice: () => void }) {
  const [query, setQuery] = useState('');
  return <View style={{ gap: 8 }}><View style={styles.typedComposer}>
    <TextInput accessibilityLabel="Patient name or record ID for this request" placeholder="Patient name or record ID" placeholderTextColor="#74877d" maxLength={200} editable={!busy} value={query} onChangeText={setQuery} style={styles.input} />
    <Pressable accessibilityRole="button" disabled={busy || !query.trim()} onPress={() => onUse(query)} style={[styles.send, (busy || !query.trim()) && styles.disabled]}><Text style={styles.sendText}>Use patient</Text></Pressable>
  </View><Pressable accessibilityRole="button" disabled={busy} onPress={onVoice}><Text style={styles.evidence}>Answer patient question by voice</Text></Pressable></View>;
}

function Evidence({ job }: { job: WorkspaceJob }) {
  const [expanded, setExpanded] = useState(false);
  return <View><Pressable onPress={() => setExpanded(!expanded)}><Text style={styles.evidence}>{expanded ? 'Hide evidence' : `Evidence · ${job.response?.answer?.citations.length ?? 0} sources`}</Text></Pressable>{expanded && <CitationList citations={job.response?.answer?.citations ?? []} />}</View>;
}

function AnswerText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return <View style={{ gap: 8 }}><Text numberOfLines={expanded ? undefined : 8} style={styles.answerText}>{text}</Text>{text.length > 450 && <Pressable onPress={() => setExpanded(!expanded)}><Text style={styles.evidence}>{expanded ? 'Show less' : 'Read full answer'}</Text></Pressable>}</View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#edf3ee' }, flex: { flex: 1 },
  pair: { flex: 1, justifyContent: 'center', padding: 28, gap: 20 }, brand: { fontSize: 30, color: '#234d3d', fontWeight: '600' },
  heading: { fontSize: 24, lineHeight: 32, color: '#234d3d' }, muted: { fontSize: 15, lineHeight: 23, color: '#556b60' },
  small: { fontSize: 12, lineHeight: 18, color: '#62776b' }, primary: { backgroundColor: '#30564b', borderRadius: 8, padding: 15, alignItems: 'center' }, primaryText: { color: '#fffdf7', fontSize: 15, fontWeight: '600' },
  code: { backgroundColor: '#fffdf7', borderWidth: 1, borderColor: '#cbdacf', borderRadius: 8, padding: 15, fontSize: 23, color: '#234d3d', letterSpacing: 4 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 22, paddingVertical: 15, borderBottomWidth: 1, borderColor: '#d4dfd7' },
  thread: { padding: 20, gap: 26 }, empty: { paddingVertical: 60, gap: 16 }, exchange: { gap: 14 },
  user: { alignSelf: 'flex-end', maxWidth: '90%', backgroundColor: '#dbe8df', borderRadius: 8, padding: 13 }, userText: { color: '#234d3d', fontSize: 15, lineHeight: 23 },
  answer: { gap: 12 }, answerText: { color: '#273d31', fontSize: 15, lineHeight: 24 }, patient: { color: '#356750', fontSize: 12, fontWeight: '600' },
  choice: { backgroundColor: '#fffdf7', borderWidth: 1, borderColor: '#cbdacf', borderRadius: 8, padding: 13, gap: 4 }, evidence: { fontSize: 13, color: '#46647a' },
  composer: { padding: 18, gap: 12, borderTopWidth: 1, borderColor: '#d4dfd7', backgroundColor: '#fffdf7' }, input: { flex: 1, minHeight: 48, maxHeight: 100, fontSize: 16, color: '#273d31', paddingHorizontal: 12, paddingVertical: 12 },
  typedComposer: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: '#d4dfd7', borderRadius: 10, backgroundColor: '#f4f7f3' },
  send: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 14, borderRadius: 8 }, sendText: { color: '#30564b', fontSize: 14, fontWeight: '600' }, disabled: { opacity: 0.45 }, error: { color: '#9a422f', fontSize: 13, lineHeight: 20 },
});
