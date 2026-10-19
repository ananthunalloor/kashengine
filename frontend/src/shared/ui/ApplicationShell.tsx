import {
  Alert,
  Anchor,
  Burger,
  Button,
  Group,
  NavLink,
  Stack,
  Text,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useRef } from "react";
import type { ReactNode } from "react";

import { csrfToken } from "../api/client";
import type { Session } from "../api/generated/types.gen";

export function ApplicationShell({ session, children }: { session: Session; children: ReactNode }) {
  const [opened, { toggle, close }] = useDisclosure();
  // Mantine's transition reset injects a style element, which our CSP blocks.
  const { setColorScheme } = useMantineColorScheme({ keepTransitions: true });
  const colorScheme = useComputedColorScheme("light", { getInitialValueInEffect: true });
  const token = csrfToken();
  const burger = useRef<HTMLButtonElement>(null);

  return (
    <div className="app-shell">
      <header className="app-header">
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={toggle}
              className="app-mobile-only"
              ref={burger}
              size="sm"
              aria-label={opened ? "Close navigation" : "Open navigation"}
              aria-expanded={opened}
              aria-controls="app-navigation"
            />
            <Anchor href="/app/" underline="never" c="inherit" fw={700} size="lg">
              Kash Engine
            </Anchor>
          </Group>
          <Group gap="xs">
            <Text size="sm" className="app-desktop-only">
              {session.username}
            </Text>
            <Button
              variant="default"
              size="compact-sm"
              onClick={() => setColorScheme(colorScheme === "dark" ? "light" : "dark")}
              aria-label="Toggle color scheme"
            >
              {colorScheme === "dark" ? "Light theme" : "Dark theme"}
            </Button>
          </Group>
        </Group>
      </header>
      <aside
        className="app-navigation"
        id="app-navigation"
        data-opened={opened}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            close();
            burger.current?.focus();
          }
        }}
      >
        <nav aria-label="Main">
          <NavLink href="/app/" label="React preview" active aria-current="page" onClick={close} />
          {session.navigation.map((item) => (
            <NavLink key={item.url} href={item.url} label={item.label} onClick={close} />
          ))}
        </nav>
        <Stack mt="auto" p="xs" gap="xs">
          <Text size="sm" c="dimmed">
            Signed in as {session.username}
          </Text>
          <form action={session.logout_url} method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value={token ?? ""} />
            <Button type="submit" variant="default" fullWidth disabled={!token}>
              Log out
            </Button>
          </form>
          {!token && (
            <Text size="xs" role="alert">
              Reload the page to enable secure logout.
            </Text>
          )}
        </Stack>
      </aside>
      <main className="app-main" id="main" tabIndex={-1}>
        {session.notice && (
          <Alert color="yellow" title="Your subscription" role="status" mb="md">
            {session.notice} <Anchor href="/account/">See your account</Anchor>.
          </Alert>
        )}
        {children}
        <Text component="footer" size="xs" c="dimmed" mt="xl" py="lg">
          Market signals are informational, not investment advice. GMP is unofficial data.
        </Text>
      </main>
    </div>
  );
}
