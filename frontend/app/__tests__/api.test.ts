import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiFetch, ApiError } from "../lib/api";

function mockFetch(status: number) {
  const res = new Response(JSON.stringify({ ok: status < 400 }), { status });
  const spy = vi.fn().mockResolvedValue(res);
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("apiFetch", () => {
  beforeEach(() => localStorage.clear());

  it("attaches the bearer token", async () => {
    const spy = mockFetch(200);
    await apiFetch("/api/v1/tasks", "tok-123");
    const [, init] = spy.mock.calls[0];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-123");
  });

  it("returns the response on success without touching the token", async () => {
    mockFetch(200);
    localStorage.setItem("blurt_token", "tok");
    const res = await apiFetch("/api/v1/tasks", "tok");
    expect(res.ok).toBe(true);
    expect(localStorage.getItem("blurt_token")).toBe("tok");
  });

  it("clears the token and throws on 401", async () => {
    mockFetch(401);
    localStorage.setItem("blurt_token", "expired");
    await expect(apiFetch("/api/v1/tasks", "expired")).rejects.toBeInstanceOf(ApiError);
    expect(localStorage.getItem("blurt_token")).toBeNull();
  });

  it("does not clear the token on other error statuses", async () => {
    mockFetch(500);
    localStorage.setItem("blurt_token", "tok");
    const res = await apiFetch("/api/v1/tasks", "tok");
    expect(res.status).toBe(500);
    expect(localStorage.getItem("blurt_token")).toBe("tok");
  });
});
