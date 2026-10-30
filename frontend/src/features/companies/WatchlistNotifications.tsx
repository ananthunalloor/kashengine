import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  markWatchlistNotificationRead,
  watchlistNotificationsQuery,
} from "../../shared/api/watchlist";
import { notify, notifyError } from "../../shared/ui/notifications";

export function WatchlistNotifications({ enabled }: { enabled: boolean }) {
  const notifications = useQuery({ ...watchlistNotificationsQuery(), enabled });

  useEffect(() => {
    if (!notifications.data?.length) return;
    for (const item of notifications.data) {
      notify({
        id: `price-alert-${item.id}`,
        title: `${item.symbol} price alert`,
        message: `${item.company_name} rose to INR ${item.triggered_price.toLocaleString("en-IN")} above your INR ${item.above_price.toLocaleString("en-IN")} threshold.`,
        tone: "info",
        href: `/companies/${item.company_id}/`,
      });
      void markWatchlistNotificationRead(item.id).catch((error: unknown) => {
        notifyError(error, "Price notification could not be acknowledged");
      });
    }
  }, [notifications.data]);

  useEffect(() => {
    if (notifications.error) notifyError(notifications.error, "Price notifications unavailable");
  }, [notifications.error]);

  return null;
}
