import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useAuth } from "../hooks/useAuth";
import { useRecorder } from "../hooks/useRecorder";

describe("useAuth", () => {
  beforeEach(() => localStorage.clear());

  it("starts with no token", () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.token).toBeNull();
  });

  it("reads an existing token from storage", () => {
    localStorage.setItem("blurt_token", "stored");
    const { result } = renderHook(() => useAuth());
    expect(result.current.token).toBe("stored");
  });

  it("login persists and exposes the token", () => {
    const { result } = renderHook(() => useAuth());
    act(() => result.current.login("abc"));
    expect(result.current.token).toBe("abc");
    expect(localStorage.getItem("blurt_token")).toBe("abc");
  });

  it("logout clears the token", () => {
    localStorage.setItem("blurt_token", "abc");
    const { result } = renderHook(() => useAuth());
    act(() => result.current.logout());
    expect(result.current.token).toBeNull();
    expect(localStorage.getItem("blurt_token")).toBeNull();
  });
});

describe("useRecorder", () => {
  const file = () => new File(["data"], "memo.webm", { type: "audio/webm" });

  it("starts idle", () => {
    const { result } = renderHook(() => useRecorder({ token: "t", onUploaded: vi.fn() }));
    expect(result.current.micActive).toBe(false);
    expect(result.current.uploading).toBe(false);
    expect(result.current.uploadError).toBeNull();
  });

  it("uploads a file and signals completion", async () => {
    const onUploaded = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    const { result } = renderHook(() => useRecorder({ token: "t", onUploaded }));

    await act(async () => { await result.current.uploadFile(file()); });

    expect(global.fetch).toHaveBeenCalledWith("/api/v1/recordings", expect.objectContaining({ method: "POST" }));
    const init = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer t");
    expect(init.body).toBeInstanceOf(FormData);
    expect(onUploaded).toHaveBeenCalledTimes(1);
    expect(result.current.uploading).toBe(false);
  });

  it("surfaces an upload error and does not signal completion", async () => {
    const onUploaded = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 413, json: async () => ({ detail: "File too large" }) });
    const { result } = renderHook(() => useRecorder({ token: "t", onUploaded }));

    await act(async () => { await result.current.uploadFile(file()); });

    expect(result.current.uploadError).toBe("File too large");
    expect(onUploaded).not.toHaveBeenCalled();
  });
});
