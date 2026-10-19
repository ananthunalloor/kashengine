import { Stack, Text, Title } from "@mantine/core";
import { createFileRoute } from "@tanstack/react-router";

function AppHome() {
  return (
    <Stack gap="md" py="xl">
      <Title order={1} tabIndex={-1}>
        React preview
      </Title>
      <Text maw={640}>
        Your account's available sections are in the navigation. These links still open the existing
        pages while their React replacements are built and checked for parity.
      </Text>
    </Stack>
  );
}

export const Route = createFileRoute("/")({ component: AppHome });
