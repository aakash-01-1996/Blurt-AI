import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DeleteAccountCard } from "../components/settings/DeleteAccountCard";

describe("DeleteAccountCard", () => {
  beforeEach(() => localStorage.clear());

  it("requires confirmation before deleting", () => {
    render(<DeleteAccountCard token="t" />);
    // No request fires until the warning is confirmed.
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    expect(
      screen.getByText(/won.t have access to your Blurts and your account will be deleted/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes, delete my account" })).toBeInTheDocument();
  });

  it("cancels without deleting", () => {
    global.fetch = vi.fn();
    render(<DeleteAccountCard token="t" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("button", { name: "Yes, delete my account" })).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("deletes the account and clears the token", async () => {
    localStorage.setItem("blurt_token", "t");
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    render(<DeleteAccountCard token="t" />);

    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete my account" }));

    await waitFor(() => expect(localStorage.getItem("blurt_token")).toBeNull());
    const [url, init] = (global.fetch as unknown as { mock: { calls: [string, RequestInit][] } })
      .mock.calls[0];
    expect(url).toBe("/api/v1/account");
    expect(init.method).toBe("DELETE");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer t");
  });

  it("surfaces an error and keeps the token on failure", async () => {
    localStorage.setItem("blurt_token", "t");
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    render(<DeleteAccountCard token="t" />);

    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete my account" }));

    await waitFor(() => expect(screen.getByText(/Could not delete your account/)).toBeInTheDocument());
    expect(localStorage.getItem("blurt_token")).toBe("t");
  });
});
