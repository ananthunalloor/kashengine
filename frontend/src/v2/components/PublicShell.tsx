import { Anchor, Button, Container, Group, Text } from "@mantine/core";
import type { ReactNode } from "react";

import { AppLink } from "../../shared/ui/AppLink";

/** Header + footer for the signed-out pages (landing, auth, 404). */
export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        flexDirection: "column",
        background: "var(--kv2-canvas)",
      }}
    >
      <header className="kv2-public-header">
        <Container size={1200} h={56}>
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Group gap={24} wrap="nowrap">
              <AppLink href="/v2/public/" className="kv2-logo">
                <span className="kv2-logo-mark">k</span>
                <span>kashengine</span>
              </AppLink>
              <Group gap={16} visibleFrom="sm">
                {["Features", "Track record", "How it works"].map((label) => (
                  <Anchor
                    key={label}
                    href={`/v2/public/#${label.toLowerCase().replace(/ /g, "-")}`}
                    size="sm"
                    c="dimmed"
                  >
                    {label}
                  </Anchor>
                ))}
              </Group>
            </Group>
            <Group gap={8} wrap="nowrap">
              <Button component={AppLink} href="/v2/public/login/" variant="subtle" color="slate">
                Log in
              </Button>
              <Button component={AppLink} href="/v2/public/signup/">
                Request access
              </Button>
            </Group>
          </Group>
        </Container>
      </header>
      <main style={{ flex: 1 }}>{children}</main>
      <footer
        style={{ borderTop: "1px solid var(--kv2-border)", background: "var(--kv2-surface)" }}
      >
        <Container size={1200} py={16}>
          <Group justify="space-between" gap={8}>
            <Text size="xs" c="dimmed">
              © kashengine · Research only. Not investment advice.
            </Text>
            <Group gap={16}>
              {["Terms", "Privacy", "Contact"].map((label) => (
                <Anchor key={label} href="#" size="xs" c="dimmed">
                  {label}
                </Anchor>
              ))}
            </Group>
          </Group>
        </Container>
      </footer>
    </div>
  );
}
