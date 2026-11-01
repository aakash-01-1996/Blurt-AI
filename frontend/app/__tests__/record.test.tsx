import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MicCard } from "../components/record/MicCard";
import { ThisWeekPanel } from "../components/record/ThisWeekPanel";
import { RecordingRow } from "../components/record/RecordingRow";
import { Recording } from "../types";

const micProps = {
  micActive: false,
  uploading: false,
  elapsed: 0,
  uploadError: null,
  onToggle: vi.fn(),
  onPickFile: vi.fn(),
};

describe("MicCard", () => {
  it("shows the record prompt when idle", () => {
    render(<MicCard {...micProps} />);
    expect(screen.getByText("Tap to record")).toBeInTheDocument();
    expect(screen.getByLabelText("Start recording")).toBeInTheDocument();
  });

  it("shows elapsed time while recording", () => {
    render(<MicCard {...micProps} micActive elapsed={41} />);
    expect(screen.getByText("Recording")).toBeInTheDocument();
    expect(screen.getByText("00:41")).toBeInTheDocument();
    expect(screen.getByLabelText("Stop recording")).toBeInTheDocument();
  });

  it("shows pause + stop controls while recording", () => {
    render(<MicCard {...micProps} micActive />);
    expect(screen.getByLabelText("Pause recording")).toBeInTheDocument();
    expect(screen.getByLabelText("Stop recording")).toBeInTheDocument();
  });

  it("shows a paused state with a resume control", () => {
    render(<MicCard {...micProps} micActive paused />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
    expect(screen.getByLabelText("Resume recording")).toBeInTheDocument();
  });

  it("wires pause, resume and stop handlers", () => {
    const onPause = vi.fn();
    const onResume = vi.fn();
    const onToggle = vi.fn();

    const { rerender } = render(
      <MicCard {...micProps} micActive onPause={onPause} onResume={onResume} onToggle={onToggle} />
    );
    fireEvent.click(screen.getByLabelText("Pause recording"));
    expect(onPause).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText("Stop recording"));
    expect(onToggle).toHaveBeenCalledTimes(1);

    rerender(
      <MicCard {...micProps} micActive paused onPause={onPause} onResume={onResume} onToggle={onToggle} />
    );
    fireEvent.click(screen.getByLabelText("Resume recording"));
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it("toggles recording on click", () => {
    const onToggle = vi.fn();
    render(<MicCard {...micProps} onToggle={onToggle} />);
    fireEvent.click(screen.getByLabelText("Start recording"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("reflects the uploading state and surfaces errors", () => {
    render(<MicCard {...micProps} uploading uploadError="Upload failed" />);
    expect(screen.getByText("Uploading…")).toBeInTheDocument();
    expect(screen.getByText("Upload failed")).toBeInTheDocument();
  });

  it("forwards a chosen file", () => {
    const onPickFile = vi.fn();
    render(<MicCard {...micProps} onPickFile={onPickFile} />);
    const input = screen.getByLabelText("or upload an audio file");
    fireEvent.change(input, { target: { files: [new File(["x"], "a.mp3", { type: "audio/mpeg" })] } });
    expect(onPickFile).toHaveBeenCalledTimes(1);
  });
});

describe("ThisWeekPanel", () => {
  const stats = { streak: 4, totalKept: 14, workLog: 8, tasks: 4, lists: 2 };

  it("renders the streak and section counts", () => {
    render(<ThisWeekPanel stats={stats} loading={false} onOpenWorkLog={vi.fn()} />);
    expect(screen.getByText("4-day streak · 14 items kept")).toBeInTheDocument();
    expect(screen.getByText("Work log")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  it("hides stats while loading", () => {
    render(<ThisWeekPanel stats={stats} loading onOpenWorkLog={vi.fn()} />);
    expect(screen.queryByText(/day streak/)).not.toBeInTheDocument();
  });

  it("opens the work log", () => {
    const onOpen = vi.fn();
    render(<ThisWeekPanel stats={stats} loading={false} onOpenWorkLog={onOpen} />);
    fireEvent.click(screen.getByText("Open this week's work log"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});

describe("RecordingRow", () => {
  const rec: Recording = { id: "r1", status: "ready", duration_s: 41, created_at: new Date().toISOString() };

  it("offers review when items are pending", () => {
    const onReview = vi.fn();
    render(<RecordingRow recording={rec} meta={{ pending: 5, kept: 0, firstSpan: "hi", sections: {} }} onReview={onReview} onDelete={vi.fn()} />);
    expect(screen.getByText("5 items to review")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Review"));
    expect(onReview).toHaveBeenCalledWith("r1");
  });

  it("shows a kept summary once reviewed", () => {
    render(<RecordingRow recording={rec} meta={{ pending: 0, kept: 7, firstSpan: null, sections: {} }} onReview={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("7 items kept")).toBeInTheDocument();
  });

  it("shows a processing label mid-pipeline", () => {
    render(<RecordingRow recording={{ ...rec, status: "splitting" }} meta={null} onReview={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Processing: splitting into items")).toBeInTheDocument();
  });

  it("deletes after confirmation", () => {
    const onDelete = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<RecordingRow recording={rec} meta={{ pending: 0, kept: 1, firstSpan: null, sections: {} }} onReview={vi.fn()} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText("Delete recording"));
    expect(onDelete).toHaveBeenCalledWith("r1");
  });

  it("does not delete when confirmation is declined", () => {
    const onDelete = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<RecordingRow recording={rec} meta={null} onReview={vi.fn()} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText("Delete recording"));
    expect(onDelete).not.toHaveBeenCalled();
  });
});
