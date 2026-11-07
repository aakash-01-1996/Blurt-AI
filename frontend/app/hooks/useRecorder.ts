"use client";

import { useRef, useState } from "react";
import { apiFetch } from "../lib/api";

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
  recordedUrl: string | null;
  start: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => Promise<void>;
  submit: () => Promise<void>;
  discard: () => void;
  uploadFile: (file: File) => Promise<void>;
}

// Mic capture, the elapsed timer, a live analyser for the waveform, and
// uploads to POST /api/v1/recordings. Stopping holds the audio for review;
// nothing is uploaded until submit() is called.
export function useRecorder({ token, onUploaded }: UseRecorderOptions): UseRecorder {
  const [micActive, setMicActive] = useState(false);
  const [paused, setPaused] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const recordedRef = useRef<{ blob: Blob; ext: string } | null>(null);

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

  function clearRecorded() {
    setRecordedUrl((url) => {
      if (url) URL.revokeObjectURL(url);
      return null;
    });
    recordedRef.current = null;
  }

  async function postForm(form: FormData): Promise<boolean> {
    setUploading(true);
    setUploadError(null);
    try {
      const res = await apiFetch("/api/v1/recordings", token, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setUploadError(body?.detail ?? `Upload failed (${res.status})`);
        return false;
      }
      onUploaded();
      return true;
    } catch {
      setUploadError("Upload failed — check your connection");
      return false;
    } finally {
      setUploading(false);
    }
  }

  async function start() {
    clearRecorded();
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

    setUploadError(null);
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

  // Stop capture and HOLD the audio for review. Does not upload.
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
    recordedRef.current = { blob, ext };
    setRecordedUrl(URL.createObjectURL(blob));
  }

  // Upload the held recording for processing.
  async function submit() {
    const rec = recordedRef.current;
    if (!rec) return;
    const form = new FormData();
    form.append("file", rec.blob, `recording.${rec.ext}`);
    const ok = await postForm(form);
    if (ok) {
      clearRecorded();
      setElapsed(0);
    }
  }

  // Throw away the held recording (re-take).
  function discard() {
    clearRecorded();
    setElapsed(0);
    setUploadError(null);
  }

  async function uploadFile(file: File) {
    const form = new FormData();
    form.append("file", file);
    await postForm(form);
  }

  return {
    micActive,
    paused,
    uploading,
    uploadError,
    elapsed,
    analyser,
    recordedUrl,
    start,
    pause,
    resume,
    stop,
    submit,
    discard,
    uploadFile,
  };
}
