import { Stack, Text, Title } from "@mantine/core";
import { createFileRoute } from "@tanstack/react-router";

function AppHome() {
  return (
    <Stack gap="md" py="xl">
      <Title order={1}>React UI foundation</Title>
      <Text maw={640}>
        This authenticated shell is ready for incremental page migration. Existing pages remain
        available while their React replacements are built and checked for parity.
      </Text>
    </Stack>
  );
}

export const Route = createFileRoute("/")({ component: AppHome });
