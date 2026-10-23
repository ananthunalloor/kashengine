import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { Notifications } from "./Notifications";
import { dismissNotification, notificationStore, notify, notifyError } from "./notifications";

afterEach(() => {
  act(() => notificationStore.getSnapshot().forEach((notice) => dismissNotification(notice.id)));
  vi.useRealTimers();
});

function show() {
  return render(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
}

it("uses Mantine notifications, announces errors, and supports dismissal", () => {
  show();
  act(() => {
    notifyError(new Error("The worker is unavailable."), "Job failed");
  });
  expect(screen.getByRole("alert")).toHaveTextContent("The worker is unavailable.");
  expect(screen.getByRole("alert")).toHaveClass("mantine-Notification-root");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss Job failed" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(document.querySelector("style")).toBeNull();
});

it("expires success messages, pauses on hover, and keeps failures until dismissed", () => {
  vi.useFakeTimers();
  show();
  act(() => {
    notify({ title: "Saved", message: "Settings saved.", tone: "success" });
    notifyError(new Error("Retry required."), "Save failed");
  });
  fireEvent.mouseEnter(screen.getByRole("status"));
  act(() => {
    vi.advanceTimersByTime(10_000);
  });
  expect(screen.getByText("Settings saved.")).toBeInTheDocument();
  fireEvent.mouseLeave(screen.getByRole("status"));
  act(() => {
    vi.advanceTimersByTime(8000);
  });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toBeInTheDocument();
});

it("deduplicates stable ids and limits the stack to five", () => {
  show();
  act(() => {
    for (let index = 0; index < 8; index++) {
      notify({ id: `task-${index}`, title: `Task ${index}`, message: "Done", tone: "success" });
    }
    notify({ id: "task-7", title: "Task 7 updated", message: "Done", tone: "success" });
  });
  expect(screen.getAllByRole("status")).toHaveLength(5);
  expect(screen.queryByText("Task 0")).not.toBeInTheDocument();
  expect(screen.getByText("Task 7 updated")).toBeInTheDocument();
});
