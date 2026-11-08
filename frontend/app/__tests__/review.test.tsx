import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FieldRows } from "../components/review/FieldRows";
import { Snippet } from "../components/review/Snippet";
import { ReviewFilters, FilterSection } from "../components/review/ReviewFilters";
import { ReviewItemCard } from "../components/review/ReviewItemCard";
import { TranscriptPanel } from "../components/review/TranscriptPanel";
import { Item, Recording } from "../types";

function mkItem(over: Partial<Item> = {}): Item {
  return {
    id: "i1",
    section: "work_log",
    status: "pending",
    span_text: "I shipped the fix",
    route_confidence: 0.9,
    start_s: null,
    end_s: null,
    fields: { accomplishment: "Shipped fix", impact: "down 30%", project: "Upload" },
    followup_question: null,
    ...over,
  };
}

describe("FieldRows", () => {
  it("renders work-log impact and project", () => {
    render(<FieldRows item={mkItem()} />);
    expect(screen.getByText("Impact")).toBeInTheDocument();
    expect(screen.getByText("down 30%")).toBeInTheDocument();
    expect(screen.getByText("Project")).toBeInTheDocument();
  });

  it("marks missing values as Not mentioned", () => {
    render(<FieldRows item={mkItem({ fields: {} })} />);
    expect(screen.getAllByText("Not mentioned").length).toBeGreaterThan(0);
  });

  it("defaults a task destination to Google Calendar", () => {
    render(<FieldRows item={mkItem({ section: "task", fields: { when: "Tue 3pm" } })} />);
    expect(screen.getByText("When")).toBeInTheDocument();
    expect(screen.getByText("Tue 3pm")).toBeInTheDocument();
    expect(screen.getByText("Google Calendar")).toBeInTheDocument();
  });
});

describe("Snippet", () => {
  it("renders a timestamp and quoted text", () => {
    render(<Snippet ts={3} text="hello there" />);
    expect(screen.getByText("0:03")).toBeInTheDocument();
    expect(screen.getByText(/hello there/)).toBeInTheDocument();
  });
});

describe("ReviewFilters", () => {
  const counts: Record<FilterSection, number> = { all: 5, work_log: 2, task: 1, list: 1, unsorted: 1 };

  it("renders available tabs", () => {
    render(<ReviewFilters counts={counts} value="all" onChange={vi.fn()} />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Work log")).toBeInTheDocument();
    expect(screen.getByText("New list")).toBeInTheDocument();
  });

  it("changes the active filter", () => {
    const onChange = vi.fn();
    render(<ReviewFilters counts={counts} value="all" onChange={onChange} />);
    fireEvent.click(screen.getByText("Work log"));
    expect(onChange).toHaveBeenCalledWith("work_log");
  });

  it("hides empty sections but always keeps All", () => {
    render(<ReviewFilters counts={{ all: 1, work_log: 0, task: 0, list: 0, unsorted: 0 }} value="all" onChange={vi.fn()} />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.queryByText("Work log")).not.toBeInTheDocument();
  });
});

describe("ReviewItemCard", () => {
  const noop = { onReview: vi.fn(), onPatch: vi.fn(), onRestore: vi.fn(), onDismiss: vi.fn() };

  it("renders the title, confidence and approve action", () => {
    render(<ReviewItemCard item={mkItem()} ts={3} {...noop} />);
    expect(screen.getByText("Shipped fix")).toBeInTheDocument();
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("Approve")).toBeInTheDocument();
  });

  it("flags work-log items missing impact", () => {
    render(<ReviewItemCard item={mkItem({ fields: { accomplishment: "Reviewed doc" } })} ts={0} {...noop} />);
    expect(screen.getByText("Approve without impact")).toBeInTheDocument();
    expect(screen.getByText(/impact missing/)).toBeInTheDocument();
  });

  it("warns before adding a task to the calendar", () => {
    render(<ReviewItemCard item={mkItem({ section: "task", fields: { title: "Dentist", when: "Tue" } })} ts={0} {...noop} />);
    expect(screen.getByText("Approve and add to calendar")).toBeInTheDocument();
    expect(screen.getByText(/adds an event to your calendar/)).toBeInTheDocument();
  });

  it("approves and rejects", () => {
    const onReview = vi.fn();
    render(<ReviewItemCard item={mkItem()} ts={0} {...noop} onReview={onReview} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onReview).toHaveBeenCalledWith("i1", "approve");
    fireEvent.click(screen.getByText("Reject"));
    expect(onReview).toHaveBeenCalledWith("i1", "reject");
  });

  it("offers Reconsider on a rejected item", () => {
    const onRestore = vi.fn();
    render(<ReviewItemCard item={mkItem({ status: "rejected" })} ts={0} {...noop} onRestore={onRestore} />);
    fireEvent.click(screen.getByText("Reconsider"));
    expect(onRestore).toHaveBeenCalledWith("i1");
  });

  it("edits fields through the inline form", async () => {
    const onPatch = vi.fn().mockResolvedValue(undefined);
    render(<ReviewItemCard item={mkItem()} ts={0} {...noop} onPatch={onPatch} />);
    fireEvent.click(screen.getByText("Edit"));
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(onPatch).toHaveBeenCalledWith("i1", expect.any(Object)));
  });

  it("shows a follow-up question when present", () => {
    render(<ReviewItemCard item={mkItem({ followup_question: "What changed?" })} ts={0} {...noop} />);
    expect(screen.getByText("Blurt asks")).toBeInTheDocument();
    expect(screen.getByText("What changed?")).toBeInTheDocument();
  });

  it("renders an approved list as a confirmation with undo", () => {
    const onDismiss = vi.fn();
    render(
      <ReviewItemCard
        item={mkItem({ section: "list", status: "approved", fields: { name: "Grocery", items: "milk, eggs" } })}
        ts={0}
        {...noop}
        onDismiss={onDismiss}
      />
    );
    expect(screen.getByText(/New list created:/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Undo"));
    expect(onDismiss).toHaveBeenCalledWith("i1");
  });

  it("offers a destination picker for unsorted items", () => {
    render(<ReviewItemCard item={mkItem({ section: "unsorted", fields: {} })} ts={0} {...noop} />);
    expect(screen.getByText("Move to")).toBeInTheDocument();
    expect(screen.getByText(/wasn.t sure where this goes/)).toBeInTheDocument();
  });
});

describe("TranscriptPanel", () => {
  const rec: Recording = { id: "r1", status: "ready", duration_s: 41, created_at: new Date().toISOString() };

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ json: async () => ({ url: "blob:audio" }) });
  });

  it("renders the transcript lines and player readout", async () => {
    const items = [mkItem({ id: "a", span_text: "first line" }), mkItem({ id: "b", span_text: "second line" })];
    render(<TranscriptPanel items={items} recording={rec} token="t" timestamps={{ a: 0, b: 10 }} />);
    expect(screen.getByText("What you said")).toBeInTheDocument();
    expect(screen.getByText("first line")).toBeInTheDocument();
    expect(screen.getByText(/0:00 \/ 0:41/)).toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });
});
