import { Alert, Badge, Button, Group, Paper, Stack, Text, Title } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { LuBookmark, LuTrash2 } from "react-icons/lu";

import { deleteWatchlistPriceAlert } from "../../shared/api/watchlist";
import type { WatchlistAlert, WatchlistItem } from "../../shared/api/watchlist";
import { notify, notifyError } from "../../shared/ui/notifications";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { BookmarkButton, PriceAlertForm } from "./WatchlistControls";

const money = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const date = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "short",
});

function PriceAlertRow({ alert }: { alert: WatchlistAlert }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => deleteWatchlistPriceAlert(alert.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["app", "watchlist"] });
      notify({ title: "Price alert deleted", message: "The alert was removed.", tone: "success" });
    },
    onError: (error) => notifyError(error, "Price alert could not be deleted"),
  });

  return (
    <Group justify="space-between" gap="xs" wrap="nowrap">
      <div>
        <Text size="sm">
          Price rises above INR {money.format(alert.above_price)}
          {alert.is_active ? "" : " - alert sent"}
        </Text>
        {alert.triggered_at && alert.triggered_price !== null && (
          <Text size="xs" c="dimmed">
            Crossed at INR {money.format(alert.triggered_price)} on{" "}
            <time dateTime={alert.triggered_at}>
              {date.format(new Date(alert.triggered_at))} IST
            </time>
          </Text>
        )}
      </div>
      <Button
        type="button"
        size="xs"
        variant="subtle"
        color="red"
        leftSection={<LuTrash2 aria-hidden="true" />}
        loading={mutation.isPending}
        aria-label={`Delete price alert above INR ${money.format(alert.above_price)}`}
        onClick={() => mutation.mutate()}
      >
        Delete
      </Button>
    </Group>
  );
}

function WatchlistCard({
  item,
  marketsAvailable,
}: {
  item: WatchlistItem;
  marketsAvailable: boolean;
}) {
  return (
    <Paper component="li" p="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Group align="flex-start">
            <div>
              <Link to="/companies/$id/" params={{ id: String(item.company.id) }}>
                <Title order={2} size="h3">
                  {item.company.name}
                </Title>
              </Link>
              <Group gap="xs" mt={4}>
                <Badge variant="light">{item.company.symbol}</Badge>
                {item.company.sector && (
                  <Text size="sm" c="dimmed">
                    {item.company.sector}
                  </Text>
                )}
              </Group>
            </div>
            <BookmarkButton companyId={item.company.id} companyName={item.company.name} />
          </Group>
          <div>
            <Text fw={700}>
              {item.quote
                ? `INR ${money.format(item.quote.price)}`
                : marketsAvailable
                  ? "No saved price"
                  : "Markets access required"}
            </Text>
            {item.quote && (
              <Text size="xs" c="dimmed">
                Latest saved price:{" "}
                <time dateTime={item.quote.as_of}>
                  {date.format(new Date(item.quote.as_of))} IST
                </time>
              </Text>
            )}
          </div>
        </Group>
        {marketsAvailable && (
          <>
            <PriceAlertForm companyId={item.company.id} marketsAvailable />
            <Stack gap="xs">
              <Text size="sm" fw={600}>
                Price alerts ({item.alerts.length})
              </Text>
              {item.alerts.length ? (
                item.alerts.map((alert) => <PriceAlertRow key={alert.id} alert={alert} />)
              ) : (
                <Text size="sm" c="dimmed">
                  No price alerts yet.
                </Text>
              )}
            </Stack>
          </>
        )}
      </Stack>
    </Paper>
  );
}

export function Watchlist({
  items,
  marketsAvailable,
}: {
  items: WatchlistItem[];
  marketsAvailable: boolean;
}) {
  const navigate = useNavigate();
  usePageTitle("Watchlist");

  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuBookmark aria-hidden="true" />
          Your saved companies
        </Text>
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={1}>Watchlist</Title>
            <Text c="dimmed" mt="sm">
              Bookmark companies and set one-shot alerts for prices rising above your thresholds.
            </Text>
          </div>
          <Button
            variant="default"
            onClick={() =>
              void navigate({
                to: "/companies/",
                search: { q: "", page: 1, index: "NIFTY_50" },
              })
            }
          >
            Browse companies
          </Button>
        </Group>
      </header>
      {!marketsAvailable && (
        <Alert color="blue" title="Market data is not available">
          You can manage bookmarks, but quotes and price alerts require Markets access.
        </Alert>
      )}
      {!items.length ? (
        <Alert color="blue" title="Your watchlist is empty">
          Browse the{" "}
          <Link to="/companies/" search={{ q: "", page: 1, index: "NIFTY_50" }}>
            company directory
          </Link>{" "}
          and bookmark a company to start tracking it.
        </Alert>
      ) : (
        <Stack component="ul" gap="md" p={0} m={0} style={{ listStyle: "none" }}>
          {items.map((item) => (
            <WatchlistCard key={item.id} item={item} marketsAvailable={marketsAvailable} />
          ))}
        </Stack>
      )}
    </Stack>
  );
}
