"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, Square } from "lucide-react";
import { useStore } from "@/lib/store";

const workflowLabels = { clinical_question: "Research", chart_update: "Document", check_screenings: "Screenings" };

export function Composer({ conversationId }: { conversationId: string }) {
  const general = useStore((s) => s.conversations.find((c) => c.id === conversationId)?.patientId === null);
  const requestMode = useStore((s) => s.requestModes[conversationId]);
  const setRequestMode = useStore((s) => s.setRequestMode);
  const routePreview = useStore((s) => s.routePreviews[conversationId]);
  const confirmRoute = useStore((s) => s.confirmRoutePreview);
  const cancelRoute = useStore((s) => s.cancelRoutePreview);
  const working = useStore((s) => s.conversations.find((c) => c.id === conversationId)?.messages.some((m) => m.pending) ?? false);
  const send = useStore((s) => s.send);
  const activate = useStore((s) => s.activateConversation);
  const speechReady = useStore((s) => s.capabilities?.speech ?? false);
  const patient = useStore((s) => {
    const conversation = s.conversations.find((c) => c.id === conversationId);
    return conversation?.patientId ? s.patients[conversation.patientId] : undefined;
  });
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [starting, setStarting] = useState(false);
  const [audio, setAudio] = useState<Blob | null>(null);
  const preview = useRef<HTMLAudioElement>(null);
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const mounted = useRef(true);
  const routing = routePreview?.status === "checking" || routePreview?.status === "ready";
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; if (recorder.current?.state === "recording") recorder.current.stop(); stream.current?.getTracks().forEach((track) => track.stop()); }; }, []);
  useEffect(() => { if (!audio) return; const url = URL.createObjectURL(audio); if (preview.current) preview.current.src = url; return () => URL.revokeObjectURL(url); }, [audio]);
  const record = async () => {
    setError("");
    if (recorder.current?.state === "recording") { recorder.current.stop(); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { setError("Recording is unavailable in this browser. Type your request instead."); return; }
    setStarting(true);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { media.getTracks().forEach((track) => track.stop()); return; }
      stream.current = media;
      const recording = new MediaRecorder(media);
      recorder.current = recording;
      const chunks: Blob[] = [];
      recording.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      recording.onstop = () => { media.getTracks().forEach((track) => track.stop()); if (!mounted.current) return; setListening(false); const blob = new Blob(chunks, { type: recording.mimeType }); if (blob.size) setAudio(blob); else setError("No audio was recorded. Try again or type your request."); };
      recording.onerror = () => { media.getTracks().forEach((track) => track.stop()); if (mounted.current) { setListening(false); setError("Recording failed. Type your request or try again."); } };
      recording.start();
      setListening(true);
    } catch { stream.current?.getTracks().forEach((track) => track.stop()); if (mounted.current) setError("Microphone access was not available. Type your request or enable microphone access in your browser."); }
    finally { if (mounted.current) setStarting(false); }
  };
  const submit = () => { const value = text.trim(); if (!value || listening || starting || audio || working || routing) return; activate(conversationId); send(value); setText(""); };
  return <div>
    {!general && <div className="mb-3 flex items-center gap-1" aria-label="Request workflow">
      {([{ label: "Auto", route: undefined }, { label: "Research", route: "clinical_question" }, { label: "Document", route: "chart_update" }, { label: "Screenings", route: "check_screenings" }] as const).map(({ label, route }) => <button key={label} type="button" aria-pressed={requestMode === route} disabled={working || routing || listening || starting || Boolean(audio)} onClick={() => setRequestMode(conversationId, route)} className={`rounded-md px-2.5 py-2 text-[12px] font-medium transition-colors disabled:opacity-50 ${requestMode === route ? "bg-white/15 text-white ring-1 ring-white/25" : "text-white/80 hover:bg-white/10 hover:text-white"}`}>{label}</button>)}
    </div>}
    {routePreview && <div className="agent-card mb-3 rounded-lg border border-hairline bg-ivory p-4 text-ink">
      {routePreview.status === "checking" ? <p role="status" className="text-[13px]">Checking which workflow fits this request…</p> : routePreview.status === "error" ? <>
        <p role="alert" className="text-[13px] leading-relaxed">{routePreview.error}</p>
        <button type="button" className="mt-3 text-[12px] font-semibold text-jade-700" onClick={() => { activate(conversationId); send(routePreview.text, routePreview.audio); }}>Try again</button>
      </> : routePreview.route && <>
        <p className="text-[13px] font-semibold">{requestMode && requestMode !== routePreview.route ? `Switch from ${workflowLabels[requestMode]} to ${workflowLabels[routePreview.route]}?` : `Use ${workflowLabels[routePreview.route]} for this request?`}</p>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{routePreview.description}</p>
        <p className="mt-3 max-h-32 overflow-y-auto break-words border-l-2 border-jade-300 pl-3 text-[13px] leading-relaxed">{routePreview.text}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="button" className="rounded-md bg-jade-700 px-3 py-2 text-[12px] font-medium text-white" onClick={() => confirmRoute(conversationId)}>{requestMode && requestMode !== routePreview.route ? `Switch to ${workflowLabels[routePreview.route]}` : `Continue with ${workflowLabels[routePreview.route]}`}</button>
          {requestMode && requestMode !== routePreview.route && <button type="button" className="text-[12px] font-medium text-jade-700" onClick={() => confirmRoute(conversationId, requestMode)}>Keep {workflowLabels[requestMode]}</button>}
        </div>
      </>}
      <button type="button" className="mt-3 text-[12px] text-ink-soft underline underline-offset-2" onClick={() => { if (routePreview.audio && routePreview.status !== "ready") setAudio(routePreview.audio); else setText(routePreview.text); cancelRoute(conversationId); }}>Cancel and edit</button>
    </div>}
    {audio && <div className="mb-3 rounded-md border border-white/25 p-3 text-[12px]"><p>Review recorded dictation</p><audio ref={preview} className="mt-2 h-8 w-full" controls /><p className="mt-2 leading-relaxed">Processing transcribes this recording and submits it using the selected workflow.</p><div className="mt-3 flex flex-wrap gap-3"><button type="button" disabled={!speechReady || working || routing} className="rounded-md bg-white px-3 py-2 font-medium text-jade-900 disabled:opacity-50" onClick={() => { activate(conversationId); send("Voice dictation", audio); setAudio(null); }}>{speechReady ? "Process dictation" : "Voice service not configured"}</button><button type="button" className="underline" onClick={() => setAudio(null)}>Discard recording</button></div></div>}
    {error && <p role="alert" className="mb-3 text-[12px] leading-relaxed">{error}</p>}
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="agent-composer rounded-lg border border-hairline-strong bg-white focus-within:border-jade-600/50">
      <textarea disabled={routing} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }} rows={2} aria-label={general ? "General clinical question" : `Message about ${patient?.name ?? "this patient"}`} placeholder={general && !listening ? "Ask a general clinical question" : listening ? "Recording… stop to review" : requestMode === "clinical_question" ? "Ask a clinical question using this patient's chart" : requestMode === "chart_update" ? "Describe findings or a chart change to draft" : requestMode === "check_screenings" ? "Ask about screening needs or care gaps" : "Ask a clinical question or describe a chart change"} className="block h-20 w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 pb-1 text-[14px] leading-relaxed text-ink outline-none placeholder:text-ink-faint" />
      <div className="flex flex-wrap items-center gap-2 px-3 pb-2">{listening && <span className="text-[11px] text-ink-faint" role="status">Recording · stop to review</span>}<div className="ml-auto flex gap-1"><button type="button" aria-label={listening ? "Stop dictation" : "Dictate"} aria-pressed={listening} disabled={!speechReady || working || routing || starting || Boolean(audio)} onClick={() => void record()} className="agent-mode grid size-8 place-items-center rounded-md text-ink-soft hover:bg-ivory-deep disabled:opacity-50">{listening ? <Square className="size-3.5" /> : <Mic className="size-4" />}</button><button type="submit" aria-label="Send" disabled={working || routing || !text.trim() || listening || starting || Boolean(audio)} className="agent-send grid size-8 place-items-center rounded-md bg-jade-600 text-white hover:bg-jade-700 disabled:bg-ivory-deep disabled:text-ink-faint"><ArrowUp className="size-4" /></button></div></div>
    </form>
  </div>;
}
