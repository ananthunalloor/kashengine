import { Notification } from "@mantine/core";
import { useEffect, useState, useSyncExternalStore } from "react";
import { LuCheck, LuInfo, LuTriangleAlert, LuX } from "react-icons/lu";

import { AppLink } from "./AppLink";
import { dismissNotification, isApplicationAlert, notificationStore } from "./notifications";
import type { Notice } from "./notifications";

const icons = { success: LuCheck, error: LuX, warning: LuTriangleAlert, info: LuInfo };

function Toast({ notice }: { notice: Notice }) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (notice.persistent || paused) return;
    const timer = window.setTimeout(() => dismissNotification(notice.id), 8000);
    return () => window.clearTimeout(timer);
  }, [notice, paused]);
  const Icon = icons[notice.tone];
  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false);
      }}
    >
      <Notification
        className="app-toast"
        data-tone={notice.tone}
        role={notice.tone === "error" ? "alert" : "status"}
        title={notice.title}
        icon={<Icon aria-hidden="true" />}
        onClose={() => dismissNotification(notice.id)}
        closeButtonProps={{ "aria-label": `Dismiss ${notice.title}` }}
        withBorder
      >
        {notice.message}
        {notice.href && (
          <AppLink className="app-toast-link" href={notice.href}>
            View task run
          </AppLink>
        )}
      </Notification>
    </div>
  );
}

export function Notifications() {
  const notices = useSyncExternalStore(notificationStore.subscribe, notificationStore.getSnapshot);
  return (
    <section className="app-notifications" aria-label="Notifications">
      {notices
        .filter((notice) => !isApplicationAlert(notice))
        .map((notice) => (
          <Toast key={notice.id} notice={notice} />
        ))}
    </section>
  );
}
