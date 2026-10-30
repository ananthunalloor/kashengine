import { Anchor, Button, Container, Paper, Stack, Text, Title } from "@mantine/core";
import { useState } from "react";
import { LuCircleCheck, LuCircleHelp, LuShieldAlert } from "react-icons/lu";

import { AppLink, PageHeader, StatusBadge } from "../components";

export function LegalPage() {
  return (
    <Container size="sm" py={32}>
      <PageHeader
        title="Legal information"
        description="Preview legal content for the redesigned public experience."
      />
      <Stack gap={12} mt="md">
        <Paper p="md" withBorder>
          <Title order={3}>Research use</Title>
          <Text size="sm" mt="xs">
            Kash Engine provides market research and informational content only. It does not execute
            trades or provide individual investment advice.
          </Text>
        </Paper>
        <Paper p="md" withBorder>
          <Title order={3}>Privacy and terms</Title>
          <Text size="sm" mt="xs">
            The complete terms, privacy notice, and regulatory disclosures will be supplied before
            this preview is used publicly.
          </Text>
        </Paper>
        <StatusBadge tone="caution">Placeholder legal copy</StatusBadge>
        <Anchor component={AppLink} href="/v2/public/">
          Return to home
        </Anchor>
      </Stack>
    </Container>
  );
}

export function SignupCompletePage() {
  return (
    <Container size="sm" py={48}>
      <Paper p="xl" withBorder>
        <Stack align="center" gap="sm" ta="center">
          <LuCircleCheck size={30} color="var(--kv2-gain)" />
          <Title order={2}>Request received</Title>
          <Text size="sm" c="dimmed">
            This preview does not create accounts. A production flow would send an email
            verification link.
          </Text>
          <Button component={AppLink} href="/v2/public/">
            Back to home
          </Button>
          <StatusBadge tone="caution">Preview only</StatusBadge>
        </Stack>
      </Paper>
    </Container>
  );
}

export function VerifyEmailPage({ token }: { token: string }) {
  const [checked, setChecked] = useState(false);
  return (
    <Container size="sm" py={48}>
      <Paper p="xl" withBorder>
        <Stack align="center" gap="sm" ta="center">
          {checked ? (
            <LuCircleCheck size={30} color="var(--kv2-gain)" />
          ) : (
            <LuCircleHelp size={30} color="var(--kv2-brand)" />
          )}
          <Title order={2}>{checked ? "Preview verified" : "Verify email"}</Title>
          <Text size="sm" c="dimmed">
            {checked
              ? "The sample token was checked locally. No account data was changed."
              : "Email verification is simulated for the v2 preview."}
          </Text>
          <Text size="xs" c="dimmed" className="kv2-mono">
            Token: {token.slice(0, 6)}…
          </Text>
          {!checked ? <Button onClick={() => setChecked(true)}>Check sample link</Button> : null}
          <Anchor component={AppLink} href="/v2/public/login/">
            Continue to log in
          </Anchor>
        </Stack>
      </Paper>
    </Container>
  );
}

export function AccessPage() {
  return (
    <Container size="sm" py={48}>
      <Paper p="xl" withBorder>
        <Stack align="center" gap="sm" ta="center">
          <LuShieldAlert size={30} color="var(--kv2-caution)" />
          <Title order={2}>Access unavailable</Title>
          <Text size="sm" c="dimmed">
            This sample account does not have access to that page. Contact your organization
            administrator in the production app.
          </Text>
          <Button component={AppLink} href="/v2/account/" variant="default">
            Review account
          </Button>
          <StatusBadge tone="caution">Preview state</StatusBadge>
        </Stack>
      </Paper>
    </Container>
  );
}

export function PublicNotFoundPage() {
  return (
    <Container size="sm" py={48}>
      <Paper p="xl" withBorder>
        <Stack align="center" gap="sm" ta="center">
          <Text fw={700} fz={36} c="dimmed">
            404
          </Text>
          <Title order={2}>Page not found</Title>
          <Text size="sm" c="dimmed">
            That page is not part of this preview.
          </Text>
          <Button component={AppLink} href="/v2/public/">
            Return to home
          </Button>
        </Stack>
      </Paper>
    </Container>
  );
}
