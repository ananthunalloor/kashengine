import { Anchor, Button, Container, Loader, Stack, Text, Title } from "@mantine/core";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { useRouter } from "@tanstack/react-router";

import { loginUrl } from "../api/client";
import { ApiError } from "../api/errors";

export function AppLoading() {
  return (
    <Container component="main" id="main" py="xl" aria-busy="true" tabIndex={-1}>
      <Stack align="center" role="status">
        <Loader aria-hidden="true" />
        <Text>Loading your account...</Text>
      </Stack>
    </Container>
  );
}

export function AppError({ error }: ErrorComponentProps) {
  const router = useRouter();
  const unauthorized = error instanceof ApiError && error.kind === "unauthorized";
  const forbidden =
    error instanceof ApiError &&
    ["feature_not_available", "subscription_required"].includes(error.code);

  return (
    <Container component="main" id="main" py="xl" tabIndex={-1}>
      <Stack role="alert">
        <Title order={1}>
          {unauthorized
            ? "Sign in to continue"
            : forbidden
              ? "Not on your account"
              : "Unable to load this page"}
        </Title>
        <Text>
          {error instanceof ApiError ? error.message : "An unexpected error occurred. Try again."}
        </Text>
        {unauthorized ? (
          <Anchor href={loginUrl()}>Go to sign in</Anchor>
        ) : (
          !forbidden && (
            <Button
              onClick={() => {
                void router.invalidate();
              }}
              w="fit-content"
            >
              Try again
            </Button>
          )
        )}
        <Anchor href="/account/">Open your account</Anchor>
      </Stack>
    </Container>
  );
}
