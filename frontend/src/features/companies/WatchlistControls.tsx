import { Alert, Button, Group, NumberInput, Text } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { LuBookmark, LuBookmarkCheck, LuPlus } from "react-icons/lu";

import {
  addWatchlistCompany,
  createWatchlistPriceAlert,
  removeWatchlistCompany,
  watchlistQuery,
} from "../../shared/api/watchlist";
import { notify, notifyError } from "../../shared/ui/notifications";

export function BookmarkButton({
  companyId,
  companyName,
}: {
  companyId: number;
  companyName: string;
}) {
  const queryClient = useQueryClient();
  const watchlist = useQuery(watchlistQuery());
  const isSaved = watchlist.data?.items.some((item) => item.company.id === companyId) ?? false;
  const mutation = useMutation({
    mutationFn: async () => {
      if (isSaved) {
        await removeWatchlistCompany(companyId);
        return false;
      }
      await addWatchlistCompany(companyId);
      return true;
    },
    onSuccess: async (watchlisted) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["app", "watchlist"] }),
        queryClient.invalidateQueries({ queryKey: ["app", "companies"] }),
      ]);
      notify({
        title: watchlisted ? "Added to watchlist" : "Removed from watchlist",
        message: `${companyName} ${watchlisted ? "is now bookmarked." : "was removed."}`,
        tone: "success",
      });
    },
    onError: (error) => notifyError(error, "Watchlist update failed"),
  });

  useEffect(() => {
    if (watchlist.error) notifyError(watchlist.error, "Watchlist unavailable");
  }, [watchlist.error]);

  return (
    <Button
      type="button"
      variant={isSaved ? "light" : "default"}
      leftSection={
        isSaved ? <LuBookmarkCheck aria-hidden="true" /> : <LuBookmark aria-hidden="true" />
      }
      loading={mutation.isPending}
      disabled={!watchlist.data || watchlist.isError}
      aria-pressed={isSaved}
      aria-label={`${isSaved ? "Remove" : "Add"} ${companyName} ${isSaved ? "from" : "to"} watchlist`}
      onClick={() => mutation.mutate()}
    >
      {isSaved ? "Bookmarked" : "Bookmark"}
    </Button>
  );
}

export function PriceAlertForm({
  companyId,
  marketsAvailable,
}: {
  companyId: number;
  marketsAvailable: boolean;
}) {
  const [abovePrice, setAbovePrice] = useState<string | number>("");
  const queryClient = useQueryClient();
  const watchlist = useQuery(watchlistQuery());
  const item = watchlist.data?.items.find((entry) => entry.company.id === companyId);
  const mutation = useMutation({
    mutationFn: () => createWatchlistPriceAlert(companyId, String(abovePrice)),
    onSuccess: async () => {
      setAbovePrice("");
      await queryClient.invalidateQueries({ queryKey: ["app", "watchlist"] });
      notify({
        title: "Price alert added",
        message: "You'll be notified when the saved price rises above your threshold.",
        tone: "success",
      });
    },
    onError: (error) => notifyError(error, "Price alert could not be added"),
  });

  if (watchlist.isError)
    return (
      <Alert color="red" title="Watchlist unavailable">
        Your bookmark status could not be loaded. Reload the page and try again.
      </Alert>
    );
  if (!marketsAvailable)
    return (
      <Text size="sm" c="dimmed">
        Price alerts are unavailable without Markets access.
      </Text>
    );
  if (!item)
    return (
      <Text size="sm" c="dimmed">
        Bookmark this company to add price alerts.
      </Text>
    );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <Group align="end" gap="xs">
        <NumberInput
          label="Notify when price rises above"
          aria-label="Notify when price rises above"
          prefix="INR "
          min={0.01}
          decimalScale={2}
          fixedDecimalScale={false}
          step={0.5}
          value={abovePrice}
          onChange={setAbovePrice}
          required
          disabled={mutation.isPending}
        />
        <Button
          type="submit"
          leftSection={<LuPlus aria-hidden="true" />}
          loading={mutation.isPending}
          disabled={!abovePrice || Number(abovePrice) <= 0}
        >
          Add alert
        </Button>
      </Group>
    </form>
  );
}
