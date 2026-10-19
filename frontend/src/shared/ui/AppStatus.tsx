import { Anchor, Button, Container, Loader, Stack, Text, Title } from "@mantine/core";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { useRouter } from "@tanstack/react-router";

import { loginUrl } from "../api/client";
import { ApiError } from "../api/errors";
import { usePageTitle } from "./usePageTitle";

export function AppLoading({
  withinShell = false,
  label = "reports",
}: { withinShell?: boolean; label?: string } = {}) {
  return (
    <Container
      component={withinShell ? "section" : "main"}
      id={withinShell ? undefined : "main"}
      py="xl"
      aria-busy="true"
      tabIndex={-1}
    >
      <Stack align="center" role="status">
        <Loader aria-hidden="true" />
        <Text>{withinShell ? `Loading ${label}...` : "Loading your account..."}</Text>
      </Stack>
    </Container>
  );
}

export function AppError({
  error,
  withinShell = false,
  section = "Reports",
  onRetry,
}: ErrorComponentProps & {
  withinShell?: boolean;
  onRetry?: () => void;
  section?:
    | "Account"
    | "Today"
    | "Reports"
    | "News"
    | "IPOs"
    | "Markets"
    | "Companies"
    | "Delivery"
    | "Task runs";
}) {
  const router = useRouter();
  const unauthorized = error instanceof ApiError && error.kind === "unauthorized";
  const notFound = error instanceof ApiError && error.kind === "not-found";
  const forbidden =
    error instanceof ApiError &&
    ["feature_not_available", "subscription_required"].includes(error.code);
  const title = unauthorized
    ? "Sign in to continue"
    : notFound
      ? section === "Reports"
        ? "Report not found"
        : section === "IPOs"
          ? "IPO not found"
          : "Page not found"
      : forbidden
        ? section === "Task runs"
          ? "Staff access required"
          : "Not on your account"
        : "Unable to load this page";
  usePageTitle(title);

  return (
    <Container
      component={withinShell ? "section" : "main"}
      id={withinShell ? undefined : "main"}
      py="xl"
      tabIndex={-1}
    >
      <Stack role="alert">
        <Title order={1} tabIndex={-1}>
          {title}
        </Title>
        <Text>
          {error instanceof ApiError ? error.message : "An unexpected error occurred. Try again."}
        </Text>
        {unauthorized ? (
          <Anchor href={loginUrl()}>Go to sign in</Anchor>
        ) : (
          !forbidden &&
          !notFound && (
            <Button
              onClick={() => {
                if (onRetry) onRetry();
                else void router.invalidate();
              }}
              w="fit-content"
            >
              Try again
            </Button>
          )
        )}
        {withinShell && (
          <Anchor
            href={
              section === "Today"
                ? "/app/dashboard/"
                : section === "Task runs"
                  ? "/app/ops/runs/"
                  : `/app/${section.toLowerCase()}/`
            }
          >
            Back to {section}
          </Anchor>
        )}
        <Anchor href="/app/account/">Open your account</Anchor>
      </Stack>
    </Container>
  );
}
