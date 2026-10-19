import { Anchor, AppShell, Container, Text, Title } from "@mantine/core";
import { createRootRoute, Link, Outlet } from "@tanstack/react-router";

function RootLayout() {
  return (
    <AppShell header={{ height: 64 }} padding="md">
      <AppShell.Header>
        <Container size="lg" h="100%" display="flex" style={{ alignItems: "center" }}>
          <Anchor component={Link} to="/" underline="never" c="inherit">
            <Title order={3}>Kash Engine</Title>
          </Anchor>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="lg">
          <Outlet />
        </Container>
      </AppShell.Main>
      <Text ta="center" size="xs" c="dimmed" py="lg">
        Market signals are informational, not investment advice.
      </Text>
    </AppShell>
  );
}

export const Route = createRootRoute({ component: RootLayout });
