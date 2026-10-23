export type Notice = {
  id: string;
  title: string;
  message: string;
  tone: "success" | "error" | "warning" | "info";
  href?: string;
  persistent?: boolean;
};

export function isApplicationAlert(notice: Notice) {
  return Boolean(notice.persistent && (notice.tone === "warning" || notice.tone === "info"));
}

let notices: Notice[] = [];
const listeners = new Set<() => void>();
let sequence = 0;

export const notificationStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getSnapshot: () => notices,
};

export function dismissNotification(id: string) {
  const remaining = notices.filter((notice) => notice.id !== id);
  if (remaining.length === notices.length) return;
  notices = remaining;
  listeners.forEach((listener) => listener());
}

export function notify(notice: Omit<Notice, "id"> & { id?: string }) {
  const id = notice.id ?? `notice-${++sequence}`;
  notices = [...notices.filter((item) => item.id !== id), { ...notice, id }].slice(-5);
  listeners.forEach((listener) => listener());
  return id;
}

export function notifyError(error: unknown, title = "Something went wrong") {
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred. Please try again.";
  notify({ id: `error-${title}-${message}`, title, message, tone: "error", persistent: true });
}
