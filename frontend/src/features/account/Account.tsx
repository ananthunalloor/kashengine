import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { LuCircleUserRound, LuKeyRound, LuPlus, LuShieldCheck, LuX } from "react-icons/lu";

import type { Account as AccountData, AccountToken } from "../../shared/api/generated/types.gen";
import { accountQuery, createToken, revokeToken } from "../../shared/api/account";
import { csrfToken, loginUrl } from "../../shared/api/client";
import { ApiError } from "../../shared/api/errors";
import { DataTable } from "../../shared/ui/DataTable";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { notify, notifyError } from "../../shared/ui/notifications";

const accountDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const tokenDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function TokenTime({ value, empty }: { value: string | null; empty: string }) {
  return value ? <time dateTime={value}>{tokenDate.format(new Date(value))} IST</time> : empty;
}

export function Account({ data }: { data: AccountData }) {
  usePageTitle("Account");
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [secret, setSecret] = useState("");
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState<AccountToken | null>(null);
  const [error, setError] = useState<{ message: string; unauthorized: boolean } | null>(null);
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  const busy = useRef(false);
  const secretPanel = useRef<HTMLDivElement>(null);
  const securityToken = csrfToken();
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (secret) secretPanel.current?.focus();
  }, [secret]);

  function showError(cause: unknown) {
    notifyError(cause, "Account action failed");
    setError({
      message:
        cause instanceof ApiError
          ? cause.message
          : "An unexpected error occurred. Reload to check your tokens.",
      unauthorized: cause instanceof ApiError && cause.kind === "unauthorized",
    });
  }

  async function refreshAccount() {
    await client.invalidateQueries({ queryKey: accountQuery().queryKey }, { throwOnError: true });
  }

  async function makeToken() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError(null);
    setNotice("");
    setSecret("");
    try {
      const result = await createToken(name.trim());
      if (!mounted.current) return;
      setSecret(result.secret);
      setName("");
      setNotice("Token created. Copy it now; it will not be shown again.");
      notify({
        title: "Token created",
        message: "Copy your token now; it will not be shown again.",
        tone: "success",
      });
      try {
        await refreshAccount();
      } catch (cause) {
        if (mounted.current) {
          showError(cause);
          setNotice(
            "Token created, but the list could not refresh. Copy the token before reloading.",
          );
        }
      }
    } catch (cause) {
      if (mounted.current) showError(cause);
    } finally {
      busy.current = false;
      if (mounted.current) setPending(false);
    }
  }

  async function confirmRevoke() {
    if (!confirm || busy.current) return;
    busy.current = true;
    setPending(true);
    setError(null);
    setNotice("");
    try {
      const token = await revokeToken(confirm.id);
      if (!mounted.current) return;
      setConfirm(null);
      setSecret("");
      setNotice(`Token ${token.display} is revoked.`);
      notify({
        title: "Token revoked",
        message: `${token.display} can no longer access the API.`,
        tone: "success",
      });
      try {
        await refreshAccount();
      } catch (cause) {
        if (mounted.current) {
          showError(cause);
          setNotice(
            "Token revoked, but the list could not refresh. Reload to see its current state.",
          );
        }
      }
    } catch (cause) {
      if (mounted.current) showError(cause);
    } finally {
      busy.current = false;
      if (mounted.current) setPending(false);
    }
  }

  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuCircleUserRound aria-hidden="true" /> Your workspace, your access
        </Text>
        <Title order={1}>Your account</Title>
        <Text c="dimmed" mt="sm">
          {data.username}
          {data.email && ` \u00b7 ${data.email}`}
        </Text>
        <Anchor href="/account/" size="sm">
          Compare with the original Account page
        </Anchor>
      </header>
      <section className="news-card" aria-labelledby="account-plan">
        <Title order={2} size="h3" id="account-plan">
          <LuShieldCheck aria-hidden="true" /> Subscription
        </Title>
        <Text mt="md" component="div">
          <span
            className="report-status"
            data-tone={
              data.state === "active" || data.state === "staff"
                ? "sent"
                : data.state === "expired" || data.state === "none"
                  ? "failed"
                  : undefined
            }
          >
            {data.state === "none"
              ? "No subscription"
              : data.state.charAt(0).toUpperCase() + data.state.slice(1)}
          </span>
        </Text>
        <Text mt="sm">
          {data.state === "staff" ? (
            "Your account is a staff account. It has all features and does not need a subscription."
          ) : data.state === "none" ? (
            "You have no subscription."
          ) : data.state === "expired" ? (
            <>
              Your {data.subscription_kind === "trial" ? "trial" : "subscription"} ended
              {data.ends_at && (
                <>
                  {" "}
                  on{" "}
                  <time dateTime={data.ends_at}>{accountDate.format(new Date(data.ends_at))}</time>
                </>
              )}
              .
            </>
          ) : data.ends_at ? (
            <>
              Your {data.state === "trial" ? "trial" : "subscription"} ends on{" "}
              <time dateTime={data.ends_at}>{accountDate.format(new Date(data.ends_at))}</time>
              {data.days_left !== null &&
                ` (${data.days_left} ${data.days_left === 1 ? "day" : "days"} left)`}
              .
            </>
          ) : (
            "Your subscription has no end date."
          )}
        </Text>
        {data.state !== "staff" && (
          <>
            {data.price && (
              <Text size="sm" c="dimmed" mt="sm">
                One period of {data.period_days} days costs {data.price} {data.currency}.
              </Text>
            )}
            {(!data.subscription_ok || data.state === "trial" || data.state === "expired") && (
              <Text size="sm" mt="sm">
                {data.contact}
              </Text>
            )}
            {!data.required && (
              <Text size="sm" c="dimmed" mt="sm">
                A subscription is not required now.
              </Text>
            )}
          </>
        )}
      </section>
      <section aria-labelledby="account-features">
        <Title order={2} size="h3" id="account-features" mb="md">
          Features
        </Title>
        <DataTable
          data={data.features}
          label="Account features"
          columns={[
            {
              id: "label",
              label: "Feature",
              value: (row) => row.label,
              render: (row) => (
                <div className="table-story">
                  <strong>{row.label}</strong>
                  <Text size="sm" c="dimmed" mt="xs">
                    {row.help}
                  </Text>
                </div>
              ),
            },
            {
              id: "access",
              label: "Access",
              value: (row) =>
                row.allowed
                  ? "Included"
                  : row.removed
                    ? "Not on your account"
                    : "Locked until you subscribe",
              render: (row) => (
                <span className="report-status" data-tone={row.allowed ? "sent" : undefined}>
                  {row.allowed
                    ? "Included"
                    : row.removed
                      ? "Not on your account"
                      : "Locked until you subscribe"}
                </span>
              ),
            },
          ]}
        />
      </section>
      <section className="news-card" aria-labelledby="account-api">
        <Title order={2} size="h3" id="account-api">
          <LuKeyRound aria-hidden="true" /> API access
        </Title>
        <Text size="sm" c="dimmed" mt="sm">
          An API token lets a program read your data from the read-only API. It has the same access
          as your account.
          {data.api_docs && (
            <>
              {" "}
              <Anchor href="/api/v1/docs">Open the API documentation</Anchor>.
            </>
          )}
        </Text>
        {!data.api_enabled && (
          <Text role="status" mt="md">
            API access is disabled. You can still revoke existing tokens.
          </Text>
        )}
        {!securityToken && (
          <Text role="alert" mt="md">
            Reload the page to enable secure token actions.
          </Text>
        )}
        {notice && (
          <Text role="status" mt="md">
            {notice}
          </Text>
        )}
        {error && (
          <div role="alert" className="account-action-error">
            <Text>{error.message}</Text>
            {error.unauthorized ? (
              <Anchor href={loginUrl()}>Go to sign in</Anchor>
            ) : (
              <Text size="sm">
                Reload to check the current token list before trying the action again.
              </Text>
            )}
          </div>
        )}
        {secret && (
          <div role="alert" className="account-secret" ref={secretPanel} tabIndex={-1}>
            <Text fw={600}>Copy this token now. The page does not show it again.</Text>
            <code>{secret}</code>
            <Button
              variant="default"
              size="compact-sm"
              leftSection={<LuX aria-hidden="true" />}
              onClick={() => setSecret("")}
            >
              Hide token
            </Button>
          </div>
        )}
        {confirm && (
          <section className="account-revoke" aria-label="Confirm revocation">
            <Text>
              Revoke {confirm.name} ({confirm.display})? Programs using it will lose access
              immediately.
            </Text>
            <Group mt="sm">
              <Button
                color="red"
                disabled={pending || !securityToken}
                onClick={() => void confirmRevoke()}
              >
                Confirm revoke
              </Button>
              <Button variant="default" disabled={pending} onClick={() => setConfirm(null)}>
                Cancel
              </Button>
            </Group>
          </section>
        )}
        <div className="account-token-table">
          <DataTable
            data={data.tokens}
            label="Your API tokens (latest 20)"
            empty={data.tokens.length ? undefined : "You have no API tokens."}
            filters={[
              {
                label: "Token state",
                value: (row) => row.state,
                options: ["active", "expired", "revoked"],
              },
            ]}
            columns={[
              { id: "name", label: "Name", value: (row) => row.name },
              {
                id: "display",
                label: "Token",
                value: (row) => row.display,
                render: (row) => <code>{row.display}</code>,
              },
              {
                id: "last_used_at",
                label: "Last used",
                value: (row) => row.last_used_at,
                render: (row) => <TokenTime value={row.last_used_at} empty="Never" />,
              },
              {
                id: "expires_at",
                label: "Ends",
                value: (row) => row.expires_at,
                render: (row) => <TokenTime value={row.expires_at} empty="No end date" />,
              },
              {
                id: "state",
                label: "State",
                value: (row) => row.state,
                render: (row) => (
                  <span
                    className="report-status"
                    data-tone={row.state === "active" ? "sent" : undefined}
                  >
                    {row.state.charAt(0).toUpperCase() + row.state.slice(1)}
                  </span>
                ),
              },
              {
                id: "actions",
                label: "Actions",
                value: () => null,
                sortable: false,
                render: (row) =>
                  row.state === "active" ? (
                    <Button
                      size="compact-xs"
                      variant="default"
                      disabled={pending || !securityToken}
                      aria-label={`Revoke ${row.name}`}
                      onClick={() => {
                        setError(null);
                        setConfirm(row);
                      }}
                    >
                      Revoke
                    </Button>
                  ) : null,
              },
            ]}
          />
        </div>
        {data.api_enabled &&
          (data.active_tokens < data.token_limit ? (
            <form
              className="account-token-form"
              onSubmit={(event) => {
                event.preventDefault();
                void makeToken();
              }}
            >
              <label htmlFor="token-name">
                Token name
                <input
                  id="token-name"
                  type="text"
                  maxLength={60}
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  disabled={pending}
                  autoComplete="off"
                />
              </label>
              <Button
                type="submit"
                disabled={pending || !securityToken || !name.trim()}
                leftSection={<LuPlus aria-hidden="true" />}
              >
                {pending ? "Saving..." : "Make token"}
              </Button>
            </form>
          ) : (
            <Text mt="md">
              You have {data.active_tokens} active tokens. Revoke one to make a new token.
            </Text>
          ))}
        {data.api_enabled && (
          <Text size="xs" c="dimmed" mt="sm">
            You can have {data.token_limit} active tokens.
            {data.token_days > 0 && ` A new token works for ${data.token_days} days.`}
          </Text>
        )}
      </section>
    </Stack>
  );
}
