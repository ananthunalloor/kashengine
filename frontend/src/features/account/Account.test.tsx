import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { Account, AccountToken } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const token: AccountToken = {
  id: 1,
  name: "Excel",
  display: "ke_12345678_\u2026",
  created_at: "2026-10-19T03:00:00Z",
  last_used_at: null,
  expires_at: null,
  state: "active",
};
const data: Account = {
  username: "member",
  email: "member@example.test",
  delivery: {
    email_verified: true,
    email_reports: false,
    telegram_connected: false,
    telegram_reports: false,
    telegram_bot_username: "kash_test_bot",
  },
  state: "trial",
  subscription_kind: "trial",
  ends_at: "2026-10-26T03:00:00Z",
  days_left: 7,
  subscription_ok: true,
  required: true,
  price: "123.50",
  currency: "INR",
  period_days: 30,
  contact: "<b>Contact the admin</b>",
  features: [
    {
      key: "reports",
      label: "Daily reports",
      help: "Daily reports and details.",
      allowed: true,
      removed: false,
    },
    { key: "news", label: "News", help: "Scored articles.", allowed: false, removed: true },
  ],
  api_enabled: true,
  api_docs: true,
  tokens: [token],
  active_tokens: 1,
  token_limit: 3,
  token_days: 30,
};
const oneTimeSecret = "one-time-token-for-ui-test";
const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showAccount({
  body = data,
  getStatus = 200,
  createStatus = 201,
  createBody = { token: { ...token, id: 2, name: "New token" }, secret: oneTimeSecret },
  revokeStatus = 200,
  refreshFails = false,
  csrf = true,
  verified = true,
  path = "/account/",
  waitForCreate,
}: {
  body?: unknown;
  getStatus?: number;
  createStatus?: number;
  createBody?: unknown;
  revokeStatus?: number;
  refreshFails?: boolean;
  csrf?: boolean;
  verified?: boolean;
  path?: string;
  waitForCreate?: Promise<void>;
} = {}) {
  if (csrf) document.cookie = "csrftoken=account-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  let created = false;
  let revoked = false;
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    let responseBody: unknown;
    let status = 200;
    if (input === "/api/app/session") {
      responseBody = {
        ...session,
        email_verified: verified,
        subscription_ok: false,
        features: [],
        navigation: verified ? session.navigation : [{ label: "Account", url: "/account/" }],
        notice: verified ? "" : "Verify your email in Account settings to unlock all features.",
      };
    } else if (input === "/api/app/account/tokens" && init?.method === "POST") {
      await waitForCreate;
      created = createStatus === 201;
      status = createStatus;
      responseBody = createBody;
    } else if (input === "/api/app/account/delivery/email/verify" && init?.method === "POST") {
      responseBody = { ...data.delivery, email_verified: false };
    } else if (input === "/api/app/account/delivery" && init?.method === "PUT") {
      responseBody = { ...data.delivery, email_reports: true };
    } else if (input === "/api/app/account/delivery/telegram/link" && init?.method === "POST") {
      responseBody = {
        url: "https://t.me/kash_test_bot?start=single-use-token",
        expires_at: "2026-10-23T06:00:00Z",
      };
    } else if (input === "/api/app/account/delivery/telegram/unlink" && init?.method === "POST") {
      responseBody = {
        ...data.delivery,
        telegram_connected: false,
        telegram_reports: false,
      };
    } else if (input.endsWith("/revoke")) {
      revoked = revokeStatus === 200;
      status = revokeStatus;
      responseBody = revoked
        ? { ...token, state: "revoked" }
        : { code: "not_found", detail: "Token not found." };
    } else {
      status = (created || revoked) && refreshFails ? 500 : getStatus;
      responseBody =
        status === 500
          ? { code: "server_error", detail: "Account refresh failed." }
          : created
            ? { ...data, tokens: [{ ...token, id: 2, name: "New token" }, token], active_tokens: 2 }
            : revoked
              ? { ...data, tokens: [{ ...token, state: "revoked" }], active_tokens: 0 }
              : body;
    }
    return new Response(JSON.stringify(responseBody), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/",
    trailingSlash: "always",
    history: createMemoryHistory({ initialEntries: [path] }),
    context: { queryClient: client },
    defaultPendingMinMs: 0,
  });
  await router.load();
  const result = render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return { client, router, fetchMock, unmount: result.unmount };
}

it.each(["/account/", "/dashboard/", "/news/"])(
  "keeps unverified users on Account and allows requesting verification from %s",
  async (path) => {
    const { fetchMock, router } = await showAccount({
      path,
      verified: false,
      body: {
        ...data,
        delivery: { ...data.delivery, email_verified: false },
        api_enabled: false,
        api_docs: false,
        features: data.features.map((feature) => ({ ...feature, allowed: false })),
      },
    });
    const button = await screen.findByRole("button", { name: "Send verification email" });
    expect(router.state.location.pathname).toBe("/account/");
    expect(screen.getByRole("checkbox", { name: /Email reports/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Link Telegram" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save report settings" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Make token" })).not.toBeInTheDocument();
    expect(
      screen.getByText(/All features are locked until you verify your email/),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.every(
        ([url]) => url === "/api/app/session" || url === "/api/app/account",
      ),
    ).toBe(true);
    fireEvent.click(button);
    expect(
      await screen.findByText(/Verification email sent. Check your inbox/),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          url === "/api/app/account/delivery/email/verify" && init?.method === "POST",
      ),
    ).toBe(true);
    expect(screen.getByRole("checkbox", { name: /Email reports/ })).toBeDisabled();
  },
);

async function makeToken() {
  fireEvent.change(await screen.findByRole("textbox", { name: "Token name" }), {
    target: { value: "New token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Make token" }));
}

it("renders subscription, access explanations and masked tokens for locked accounts", async () => {
  await showAccount();
  expect(
    await screen.findByRole("heading", { level: 1, name: "Your account" }),
  ).not.toHaveAttribute("tabindex");
  expect(document.title).toBe("Account | Kash Engine");
  expect(screen.getByRole("link", { name: "Account", current: "page" })).toHaveAttribute(
    "href",
    "/account/",
  );
  expect(screen.getByText("member \u00b7 member@example.test")).toBeInTheDocument();
  expect(screen.getByText(/Your trial ends/)).toHaveTextContent("26 October 2026 (7 days left)");
  expect(screen.getByText(/One period/)).toHaveTextContent("123.50 INR");
  expect(screen.getByText("<b>Contact the admin</b>")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Included" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Not on your account" })).toBeInTheDocument();
  expect(screen.getByText(token.display)).toBeInTheDocument();
  expect(screen.getByText("Never")).toBeInTheDocument();
  expect(screen.getByText("No end date")).toBeInTheDocument();
  expect(document.querySelector("b")).toBeNull();
  expect(document.querySelector("style")).toBeNull();
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("saves selected report channels using the session CSRF token", async () => {
  const { fetchMock } = await showAccount();
  fireEvent.click(await screen.findByRole("checkbox", { name: /Email reports/ }));
  fireEvent.click(screen.getByRole("button", { name: "Save report settings" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/app/account/delivery",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ email_reports: true, telegram_reports: false }),
      }),
    ),
  );
  const sent = fetchMock.mock.calls.find(([path]) => path === "/api/app/account/delivery")?.[1];
  expect(new Headers(sent?.headers).get("X-CSRFToken")).toBe("account-test-csrf");
});

it("creates a one-time Telegram link", async () => {
  await showAccount();
  fireEvent.click(await screen.findByRole("button", { name: "Link Telegram" }));
  expect(
    await screen.findByRole("link", { name: "Open Telegram to finish linking" }),
  ).toHaveAttribute("href", "https://t.me/kash_test_bot?start=single-use-token");
});

it("disconnects a linked Telegram account", async () => {
  const connected = {
    ...data,
    delivery: {
      ...data.delivery,
      telegram_connected: true,
      telegram_reports: true,
    },
  };
  const { fetchMock } = await showAccount({ body: connected });
  fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/app/account/delivery/telegram/unlink",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

it("creates once, sends CSRF, refreshes metadata and never stores the secret in Query caches", async () => {
  const { client, fetchMock } = await showAccount();
  await makeToken();
  const code = await screen.findByText(oneTimeSecret);
  expect(code.closest('[role="alert"]')).toHaveFocus();
  expect(await screen.findByText("New token")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/app/account/tokens",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "New token" }),
      credentials: "same-origin",
    }),
  );
  const sent = fetchMock.mock.calls.find(([path]) => path === "/api/app/account/tokens")?.[1];
  expect(new Headers(sent?.headers).get("X-CSRFToken")).toBe("account-test-csrf");
  expect(
    JSON.stringify(
      client
        .getQueryCache()
        .getAll()
        .map((query) => query.state.data),
    ),
  ).not.toContain(oneTimeSecret);
  expect(client.getMutationCache().getAll()).toHaveLength(0);
  expect(JSON.stringify(localStorage)).not.toContain(oneTimeSecret);
  expect(JSON.stringify(sessionStorage)).not.toContain(oneTimeSecret);
  fireEvent.click(screen.getByRole("button", { name: "Hide token" }));
  expect(screen.queryByText(oneTimeSecret)).not.toBeInTheDocument();
});

it("discards the one-time secret on React navigation and never replays creation", async () => {
  const { router, fetchMock } = await showAccount();
  await makeToken();
  await screen.findByText(oneTimeSecret);
  await router.navigate({ to: "/" });
  await screen.findByRole("heading", { name: /Less noise/, level: 1 });
  await router.navigate({ to: "/account/" });
  await screen.findByRole("heading", { name: "Your account", level: 1 });
  expect(screen.queryByText(oneTimeSecret)).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([path]) => path === "/api/app/account/tokens")).toHaveLength(
    1,
  );
});

it("prevents duplicate submissions while a creation is pending", async () => {
  let finish!: () => void;
  const waitForCreate = new Promise<void>((resolve) => {
    finish = resolve;
  });
  const { fetchMock } = await showAccount({ waitForCreate });
  const input = await screen.findByRole("textbox", { name: "Token name" });
  fireEvent.change(input, { target: { value: "New token" } });
  const form = input.closest("form")!;
  fireEvent.submit(form);
  fireEvent.submit(form);
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/app/account/tokens"),
    ).toHaveLength(1),
  );
  expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
  finish();
  expect(await screen.findByText(oneTimeSecret)).toBeInTheDocument();
});

it("requires confirmation, cancels safely and refreshes after revocation", async () => {
  const { fetchMock } = await showAccount();
  fireEvent.click(await screen.findByRole("button", { name: "Revoke Excel" }));
  expect(screen.getByRole("region", { name: "Confirm revocation" })).toHaveTextContent(
    "lose access immediately",
  );
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(fetchMock.mock.calls.some(([path]) => path.endsWith("/revoke"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Revoke Excel" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm revoke" }));
  expect(await screen.findByRole("cell", { name: "Revoked" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Confirm revocation" })).not.toBeInTheDocument();
  const sent = fetchMock.mock.calls.find(([path]) => path.endsWith("/revoke"))?.[1];
  expect(new Headers(sent?.headers).get("X-CSRFToken")).toBe("account-test-csrf");
});

it("retains the secret and announces partial success if metadata refresh fails", async () => {
  await showAccount({ refreshFails: true });
  await makeToken();
  expect(await screen.findByText(oneTimeSecret)).toBeInTheDocument();
  expect(
    await screen.findByText(/Token created, but the list could not refresh/),
  ).toBeInTheDocument();
  expect(screen.getByText("Account refresh failed.")).toBeInTheDocument();
});

it.each([401, 403, 422, 429, 500])(
  "surfaces creation failure %s without a secret or automatic retry",
  async (status) => {
    const { fetchMock } = await showAccount({
      createStatus: status,
      createBody: {
        code: status === 403 ? "csrf_failed" : "failed",
        detail: "Token creation failed.",
      },
    });
    await makeToken();
    expect(await screen.findByText("Token creation failed.")).toBeInTheDocument();
    expect(screen.queryByText(oneTimeSecret)).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/app/account/tokens"),
    ).toHaveLength(1);
    expect(!!screen.queryByRole("link", { name: "Go to sign in" })).toBe(status === 401);
  },
);

it("shows revocation errors without falsely marking the token revoked", async () => {
  await showAccount({ revokeStatus: 404 });
  fireEvent.click(await screen.findByRole("button", { name: "Revoke Excel" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm revoke" }));
  expect(await screen.findByText("Token not found.")).toBeInTheDocument();
  expect(screen.queryByRole("cell", { name: "Revoked" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
});

it("allows revocation while API access is disabled but hides token creation and API docs", async () => {
  await showAccount({ body: { ...data, api_enabled: false, api_docs: false } });
  expect(await screen.findByText(/API access is disabled/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revoke Excel" })).toBeEnabled();
  expect(screen.queryByRole("textbox", { name: "Token name" })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Open the API documentation" }),
  ).not.toBeInTheDocument();
});

it("disables secure actions without CSRF and explains the active-token limit", async () => {
  await showAccount({ csrf: false, body: { ...data, active_tokens: 3 } });
  expect(
    await screen.findByText("Reload the page to enable secure token actions."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revoke Excel" })).toBeDisabled();
  expect(
    screen.getByText("You have 3 active tokens. Revoke one to make a new token."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "Token name" })).not.toBeInTheDocument();
});

it.each([
  ["active", "Your subscription has no end date."],
  ["expired", "Your trial ended"],
  ["none", "You have no subscription."],
  ["staff", "Your account is a staff account."],
])("renders subscription state %s", async (state, text) => {
  await showAccount({
    body: { ...data, state, ends_at: state === "active" ? null : data.ends_at },
  });
  const subscription = within(await screen.findByRole("region", { name: "Subscription" }));
  expect(subscription.getByText(new RegExp(text.replaceAll(".", "\\.")))).toBeInTheDocument();
});

it("rejects contract drift and gives an Account-specific recovery route", async () => {
  await showAccount({ body: {} });
  expect(await screen.findByRole("alert")).toHaveTextContent("The Account response does not match");
  expect(screen.getByRole("link", { name: "Back to Account" })).toHaveAttribute(
    "href",
    "/account/",
  );
});

it("does not claim success for a malformed creation response", async () => {
  await showAccount({ createBody: { unexpected: true } });
  await makeToken();
  expect(await screen.findByText(/Check your tokens before trying again/)).toBeInTheDocument();
  expect(screen.queryByText(oneTimeSecret)).not.toBeInTheDocument();
});

it("searches and filters the bounded token table before paginating", async () => {
  const tokens = Array.from({ length: 20 }, (_, index) => ({
    ...token,
    id: index + 1,
    name: `Token ${String(index).padStart(2, "0")}`,
    state: index < 10 ? "active" : "expired",
  }));
  await showAccount({ body: { ...data, tokens, active_tokens: 10 } });
  const table = within(await screen.findByRole("table", { name: "Your API tokens (latest 20)" }));
  expect(table.getAllByRole("row")).toHaveLength(11);
  expect(table.queryByRole("cell", { name: "Token 19" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(await table.findByRole("cell", { name: "Token 19" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Token state" }), {
    target: { value: "active" },
  });
  expect(await table.findByRole("cell", { name: "Token 00" })).toBeInTheDocument();
  expect(table.queryByRole("cell", { name: "Token 19" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox", { name: "Search Your API tokens (latest 20)" }), {
    target: { value: "Token 09" },
  });
  expect(table.getAllByRole("row")).toHaveLength(2);
  expect(table.getByRole("cell", { name: "Token 09" })).toBeInTheDocument();
});

it("shows network failures without retrying a potentially successful creation", async () => {
  const { fetchMock } = await showAccount();
  fetchMock.mockRejectedValueOnce(new TypeError("Network unavailable"));
  await makeToken();
  expect(await screen.findByRole("alert")).toHaveTextContent(/network|connect/i);
  expect(fetchMock.mock.calls.filter(([path]) => path === "/api/app/account/tokens")).toHaveLength(
    1,
  );
  expect(screen.queryByText(oneTimeSecret)).not.toBeInTheDocument();
});
