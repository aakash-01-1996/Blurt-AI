"use client";

import { useRef, useState } from "react";

interface UseRecorderOptions {
  token: string;
  onUploaded: () => void;
}

interface UseRecorder {
  micActive: boolean;
  paused: boolean;
  uploading: boolean;
  uploadError: string | null;
  elapsed: number;
  analyser: AnalyserNode | null;
  start: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
}

// Mic capture, the elapsed timer, a live analyser for the waveform, and
// uploads to POST /api/v1/recordings.
export function useRecorder({ token, onUploaded }: UseRecorderOptions): UseRecorder {
  const [micActive, setMicActive] = useState(false);
  const [paused, setPaused] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  function startTimer() {
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  }
  function stopTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }

  function teardownAudio() {
    setAnalyser(null);
    if (audioCtxRef.current) {
      void audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
  }

  async function postForm(form: FormData) {
    setUploading(true);
    setUploadError(null);
    try {
      const res = await fetch("/api/v1/recordings", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setUploadError(body?.detail ?? `Upload failed (${res.status})`);
      } else {
        onUploaded();
      }
    } catch {
      setUploadError("Upload failed — check your connection");
    } finally {
      setUploading(false);
    }
  }

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
    const mr = new MediaRecorder(stream, { mimeType });
    chunksRef.current = [];
    mr.ondataavailable = (e) => chunksRef.current.push(e.data);
    mr.start(100);
    mediaRef.current = mr;

    // Live audio analyser for the waveform (not connected to output → no feedback).
    try {
      const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const node = ctx.createAnalyser();
      node.fftSize = 256;
      node.smoothingTimeConstant = 0.8;
      source.connect(node);
      audioCtxRef.current = ctx;
      setAnalyser(node);
    } catch {
      setAnalyser(null); // waveform falls back to a resting animation
    }

    setMicActive(true);
    setPaused(false);
    setElapsed(0);
    startTimer();
  }

  function pause() {
    if (!mediaRef.current || mediaRef.current.state !== "recording") return;
    mediaRef.current.pause();
    stopTimer();
    setPaused(true);
  }

  function resume() {
    if (!mediaRef.current || mediaRef.current.state !== "paused") return;
    mediaRef.current.resume();
    startTimer();
    setPaused(false);
  }

  async function stop() {
    if (!mediaRef.current) return;
    const mr = mediaRef.current;
    mr.stop();
    mr.stream.getTracks().forEach((t) => t.stop());
    stopTimer();
    teardownAudio();
    await new Promise<void>((res) => { mr.onstop = () => res(); });
    setMicActive(false);
    setPaused(false);

    const mimeType = chunksRef.current[0]?.type ?? "audio/webm";
    const ext = mimeType.includes("mp4") ? "mp4" : "webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });
    const form = new FormData();
    form.append("file", blob, `recording.${ext}`);
    await postForm(form);
  }

  async function uploadFile(file: File) {
    const form = new FormData();
    form.append("file", file);
    await postForm(form);
  }

  return { micActive, paused, uploading, uploadError, elapsed, analyser, start, pause, resume, stop, uploadFile };
}
