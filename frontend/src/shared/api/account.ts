import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import {
  zAccount,
  zAccountDelivery,
  zAccountToken,
  zTelegramLinkResponse,
  zTokenCreated,
} from "./generated/zod.gen";

export function accountQuery() {
  return queryOptions({
    queryKey: ["app", "account"],
    queryFn: async ({ signal }) => {
      const result = zAccount.safeParse(await appRequest("/api/app/account", { signal }));
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Account response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}

// Do not use a mutation cache: the creation response contains a one-time secret.
export async function createToken(name: string) {
  const result = zTokenCreated.safeParse(
    await appRequest("/api/app/account/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
  if (!result.success)
    throw new ApiError(
      "contract",
      "The token response does not match this app. Check your tokens before trying again.",
    );
  return result.data;
}

export async function revokeToken(id: number) {
  const result = zAccountToken.safeParse(
    await appRequest(`/api/app/account/tokens/${id}/revoke`, {
      method: "POST",
    }),
  );
  if (!result.success)
    throw new ApiError(
      "contract",
      "The revocation response does not match this app. Reload to check the token state.",
    );
  return result.data;
}

export async function updateDelivery(emailReports: boolean, telegramReports: boolean) {
  const result = zAccountDelivery.safeParse(
    await appRequest("/api/app/account/delivery", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_reports: emailReports, telegram_reports: telegramReports }),
    }),
  );
  if (!result.success)
    throw new ApiError("contract", "The delivery settings response does not match this app.");
  return result.data;
}

export async function createTelegramLink() {
  const result = zTelegramLinkResponse.safeParse(
    await appRequest("/api/app/account/delivery/telegram/link", { method: "POST" }),
  );
  if (!result.success)
    throw new ApiError("contract", "The Telegram link response does not match this app.");
  return result.data;
}

export async function unlinkTelegram() {
  const result = zAccountDelivery.safeParse(
    await appRequest("/api/app/account/delivery/telegram/unlink", { method: "POST" }),
  );
  if (!result.success)
    throw new ApiError("contract", "The Telegram settings response does not match this app.");
  return result.data;
}

export async function sendEmailVerification() {
  const result = zAccountDelivery.safeParse(
    await appRequest("/api/app/account/delivery/email/verify", { method: "POST" }),
  );
  if (!result.success)
    throw new ApiError("contract", "The email verification response does not match this app.");
  return result.data;
}
