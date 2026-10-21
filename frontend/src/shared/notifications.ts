export type AppNotification = {
  title: string;
  message: string;
  tone: "success" | "error" | "warning" | "info";
  href?: string;
};

export const APP_NOTIFICATION_EVENT = "app:notification";

export function publishNotification(notification: AppNotification) {
  window.dispatchEvent(
    new CustomEvent<AppNotification>(APP_NOTIFICATION_EVENT, { detail: notification }),
  );
}
