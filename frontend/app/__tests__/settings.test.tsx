import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SettingsPage } from "../components/pages/SettingsPage";

describe("SettingsPage", () => {
  beforeEach(() => {
    // jsdom has no object-URL support.
    (URL as unknown as { createObjectURL: () => string }).createObjectURL = vi.fn(() => "blob:x");
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = vi.fn();
  });

  it("renders the export card", () => {
    render(<SettingsPage token="t" />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Export your data")).toBeInTheDocument();
  });

  it("fetches the export when clicked", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ recordings: [] }) });
    render(<SettingsPage token="t" />);
    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));
    const calls = (global.fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock
      .calls;
    await waitFor(() => expect(calls.some(([url]) => url === "/api/v1/export")).toBe(true));
    const exportCall = calls.find(([url]) => url === "/api/v1/export")!;
    expect(new Headers(exportCall[1].headers).get("Authorization")).toBe("Bearer t");
  });

  it("surfaces an export error", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) });
    render(<SettingsPage token="t" />);
    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));
    await waitFor(() => expect(screen.getByText(/Export failed/)).toBeInTheDocument());
  });
});
