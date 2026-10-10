"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, Square } from "lucide-react";
import { useStore } from "@/lib/store";

export function Composer({ conversationId }: { conversationId: string }) {
  const send = useStore((s) => s.send);
  const activate = useStore((s) => s.activateConversation);
  const patient = useStore((s) => {
    const conversation = s.conversations.find((c) => c.id === conversationId);
    return conversation ? s.patients[conversation.patientId] : undefined;
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
  const submit = () => { const value = text.trim(); if (!value || listening || starting || audio) return; activate(conversationId); send(value); setText(""); };
  return <div>
    {audio && <div className="mb-3 rounded-md border border-white/25 p-3 text-[12px]"><p>Review recorded dictation</p><audio ref={preview} className="mt-2 h-8 w-full" controls /><p className="mt-2 leading-relaxed">Voice transcription is not connected yet. Review or discard this recording; no transcript or chart changes have been created.</p><div className="mt-3 flex flex-wrap gap-3"><button type="button" disabled title="The backend speech adapter is not implemented yet" className="rounded-md bg-white/70 px-3 py-2 font-medium text-jade-900">Transcription unavailable</button><button type="button" className="underline" onClick={() => setAudio(null)}>Discard recording</button></div></div>}
    {error && <p role="alert" className="mb-3 text-[12px] leading-relaxed">{error}</p>}
    <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="agent-composer rounded-lg border border-hairline-strong bg-white focus-within:border-jade-600/50">
      <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }} rows={1} aria-label={`Message about ${patient?.name ?? "this patient"}`} placeholder={listening ? "Recording… stop to review" : "Ask a question or describe a chart change"} className="field-sizing-content block max-h-48 min-h-12 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[14px] leading-relaxed text-ink outline-none placeholder:text-ink-faint" />
      <div className="flex flex-wrap items-center gap-2 px-3 pb-2"><span className="text-[11px] text-ink-faint" role="status">{listening ? "Recording · click stop to review" : "Draft → Review → Approve"}</span><div className="ml-auto flex gap-1"><button type="button" aria-label={listening ? "Stop dictation" : "Dictate"} aria-pressed={listening} disabled={starting || Boolean(audio)} onClick={() => void record()} className="agent-mode grid size-8 place-items-center rounded-md text-ink-soft hover:bg-ivory-deep disabled:opacity-50">{listening ? <Square className="size-3.5" /> : <Mic className="size-4" />}</button><button type="submit" aria-label="Send" disabled={!text.trim() || listening || starting || Boolean(audio)} className="agent-send grid size-8 place-items-center rounded-md bg-jade-600 text-white hover:bg-jade-700 disabled:bg-ivory-deep disabled:text-ink-faint"><ArrowUp className="size-4" /></button></div></div>
    </form>
  </div>;
}
