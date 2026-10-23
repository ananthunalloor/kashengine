import { Alert, Anchor, Stack } from "@mantine/core";
import { useSyncExternalStore } from "react";
import { LuInfo, LuTriangleAlert } from "react-icons/lu";

import { AppLink } from "./AppLink";
import { dismissNotification, isApplicationAlert, notificationStore } from "./notifications";

export function ApplicationAlerts() {
  const notices = useSyncExternalStore(notificationStore.subscribe, notificationStore.getSnapshot);
  const alerts = notices.filter(isApplicationAlert);
  if (!alerts.length) return null;
  return (
    <Stack component="section" aria-label="Application alerts" mb="md">
      {alerts.map((notice) => (
        <Alert
          key={notice.id}
          title={notice.title}
          color={notice.tone === "warning" ? "yellow" : "blue"}
          icon={
            notice.tone === "warning" ? (
              <LuTriangleAlert aria-hidden="true" />
            ) : (
              <LuInfo aria-hidden="true" />
            )
          }
          role="status"
          withCloseButton
          closeButtonLabel={`Dismiss ${notice.title}`}
          onClose={() => dismissNotification(notice.id)}
        >
          {notice.message}
          {notice.href && (
            <Anchor component={AppLink} href={notice.href} ml="xs">
              View task run
            </Anchor>
          )}
        </Alert>
      ))}
    </Stack>
  );
}
