import {
  Anchor,
  Badge,
  Box,
  Button,
  Container,
  Divider,
  Grid,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { LineChart } from "@mantine/charts";
import type { ReactNode } from "react";
import {
  LuArrowRight,
  LuBuilding2,
  LuCode,
  LuFileText,
  LuLayoutDashboard,
  LuMail,
  LuNewspaper,
  LuRocket,
  LuScale,
  LuSend,
  LuShieldCheck,
  LuTrendingUp,
  LuUserCheck,
} from "react-icons/lu";

import {
  AppLink,
  Delta,
  DirectionBadge,
  InfoTip,
  Panel,
  ScoreBar,
  StatusBadge,
  StrengthMeter,
  formatDate,
  formatNumber,
  formatSigned,
} from "../components";
import { capabilities, channels, sampleBrief, steps, trackRecord } from "../mock/public";

const capabilityIcons: Record<string, ReactNode> = {
  news: <LuNewspaper size={16} />,
  outlook: <LuTrendingUp size={16} />,
  ipos: <LuRocket size={16} />,
  companies: <LuBuilding2 size={16} />,
  brief: <LuFileText size={16} />,
  delivery: <LuSend size={16} />,
};

const channelIcons: Record<string, ReactNode> = {
  web: <LuLayoutDashboard size={16} />,
  email: <LuMail size={16} />,
  telegram: <LuSend size={16} />,
  api: <LuCode size={16} />,
};

const principles = [
  {
    icon: <LuFileText size={16} />,
    title: "Explanations with every signal",
    body: "Scores come with a reason, so you can judge the input yourself.",
  },
  {
    icon: <LuScale size={16} />,
    title: "Accuracy against a baseline",
    body: "Hit rates are published next to a simple benchmark, good days and bad.",
  },
  {
    icon: <LuUserCheck size={16} />,
    title: "Your judgment decides",
    body: "Kash Engine never places trades or tells you what to buy or sell.",
  },
];

function Section({
  id,
  eyebrow,
  title,
  description,
  children,
  muted,
}: {
  id?: string;
  eyebrow: string;
  title: string;
  description?: string;
  children: ReactNode;
  muted?: boolean;
}) {
  return (
    <Box
      component="section"
      id={id}
      py={56}
      style={{
        borderTop: "1px solid var(--kv2-border)",
        background: muted ? "var(--kv2-surface-muted)" : undefined,
        scrollMarginTop: 64,
      }}
    >
      <Container size={1200}>
        <Stack gap={4} mb={24} maw={640}>
          <span className="kv2-eyebrow">{eyebrow}</span>
          <Title order={2} fz={24}>
            {title}
          </Title>
          {description ? <Text c="dimmed">{description}</Text> : null}
        </Stack>
        {children}
      </Container>
    </Box>
  );
}

function BriefPreview() {
  const { outlook, closes, news } = sampleBrief;
  return (
    <Panel
      title="Morning brief"
      info="An illustrative example of the daily brief. All companies, indices and numbers are sample data."
      actions={
        <StatusBadge tone="outline" size="xs">
          Sample · {formatDate(sampleBrief.date)} · {sampleBrief.edition}
        </StatusBadge>
      }
      footer={
        <Text size="xs" c="dimmed">
          Delivered on the web, by email and on Telegram.
        </Text>
      }
    >
      <Stack gap={16}>
        <Stack gap={6}>
          <Group justify="space-between" gap={8}>
            <Group gap={4}>
              <span className="kv2-eyebrow">Market outlook</span>
              <InfoTip>
                A direction estimate for the benchmark index made before the open. Strength reflects
                how strongly the signals agree — it is not a probability of profit.
              </InfoTip>
            </Group>
            <DirectionBadge direction={outlook.direction} label={outlook.label} />
          </Group>
          <StrengthMeter score={outlook.strength} />
          <Text size="xs" c="dimmed">
            {outlook.note}
          </Text>
        </Stack>

        <Divider />

        <Stack gap={6}>
          <span className="kv2-eyebrow">Previous closes</span>
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing={8}>
            {closes.map((close) => (
              <Box
                key={close.symbol}
                p={8}
                style={{ border: "1px solid var(--kv2-border)", borderRadius: 4 }}
              >
                <Text size="xs" c="dimmed" truncate>
                  {close.name}
                </Text>
                <Text fw={600} className="kv2-num">
                  {formatNumber(close.last, 2)}
                </Text>
                <Delta value={close.changePct} size="xs" />
              </Box>
            ))}
          </SimpleGrid>
        </Stack>

        <Divider />

        <Stack gap={8}>
          <Group gap={4}>
            <span className="kv2-eyebrow">Scored news</span>
            <InfoTip>
              Each item gets a sentiment score from −1 (negative) to +1 (positive) and a one-line
              reason.
            </InfoTip>
          </Group>
          {news.map((item) => (
            <Group key={item.id} justify="space-between" align="flex-start" gap={12} wrap="nowrap">
              <Stack gap={2} style={{ minWidth: 0 }}>
                <Text size="sm" fw={500} lineClamp={2}>
                  {item.headline}
                </Text>
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {item.reason}
                </Text>
              </Stack>
              <Stack gap={2} align="flex-end" style={{ flexShrink: 0 }}>
                <ScoreBar score={item.score} width={72} />
                <Text
                  size="xs"
                  fw={600}
                  className={`kv2-num ${item.score >= 0 ? "kv2-gain" : "kv2-loss"}`}
                >
                  {item.score >= 0 ? "▲" : "▼"} {formatSigned(item.score)}
                </Text>
              </Stack>
            </Group>
          ))}
        </Stack>
      </Stack>
    </Panel>
  );
}

function Hero() {
  return (
    <Box component="section" py={{ base: 40, md: 64 }}>
      <Container size={1200}>
        <Grid gutter={40} align="center">
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Stack gap={20}>
              <Group gap={8}>
                <StatusBadge tone="brand" size="xs">
                  Built for Indian markets
                </StatusBadge>
                <StatusBadge tone="outline" size="xs">
                  Powered by a local AI model
                </StatusBadge>
              </Group>
              <Title order={1} fz={{ base: 32, md: 44 }} lh={1.1}>
                Less noise. More perspective.
              </Title>
              <Text size="lg" c="dimmed" maw={520}>
                A clearer view of Indian markets. Scored news, a daily market outlook, IPO and
                company research — in one short brief every morning.
              </Text>
              <Group gap={8}>
                <Button
                  component={AppLink}
                  href="/v2/public/signup/"
                  size="md"
                  rightSection={<LuArrowRight size={16} />}
                >
                  Request access
                </Button>
                <Button component={AppLink} href="/v2/public/login/" size="md" variant="default">
                  Log in
                </Button>
              </Group>
              <Group gap={6} wrap="nowrap">
                <LuShieldCheck size={14} color="var(--kv2-text-muted)" />
                <Text size="xs" c="dimmed">
                  Research only — no trading, no buy/sell recommendations. Access is by invite.
                </Text>
              </Group>
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 6 }}>
            <BriefPreview />
          </Grid.Col>
        </Grid>
      </Container>
    </Box>
  );
}

function Features() {
  return (
    <Section
      id="features"
      eyebrow="Features"
      title="One engine. The whole picture."
      description="Everything you need for a calm start to the trading day, with explanations instead of hype."
    >
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing={12}>
        {capabilities.map((capability) => (
          <div key={capability.key} className="kv2-panel" style={{ padding: 16 }}>
            <Stack gap={8}>
              <ThemeIcon variant="light" color="indigo" size={32} radius="sm">
                {capabilityIcons[capability.key]}
              </ThemeIcon>
              <Text fw={600}>{capability.title}</Text>
              <Text size="sm" c="dimmed">
                {capability.body}
              </Text>
              <Group gap={6}>
                {capability.tags.map((tag) => (
                  <Badge key={tag} variant="outline" color="slate" size="sm">
                    {tag}
                  </Badge>
                ))}
              </Group>
            </Stack>
          </div>
        ))}
      </SimpleGrid>
    </Section>
  );
}

function TrackRecord() {
  const { accuracy, baseline, hits, windowSessions, rolling } = trackRecord;
  return (
    <Section
      id="track-record"
      eyebrow="Track record"
      title="Research tools. Not a crystal ball."
      description="Every outlook is checked against the actual close and compared with a simple baseline. Results vary; past accuracy does not predict future results."
      muted
    >
      <Grid gutter={16}>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Panel
            title="Direction accuracy"
            info="Share of sessions where the pre-open direction matched the index's actual close-to-close move. Sample figures for illustration."
          >
            <Stack gap={12}>
              <div>
                <Text fz={36} fw={700} className="kv2-num" lh={1.1}>
                  {accuracy.toFixed(1)}%
                </Text>
                <Text size="xs" c="dimmed">
                  {hits} of {windowSessions} sessions (sample window)
                </Text>
              </div>
              <Group justify="space-between">
                <Group gap={4}>
                  <Text size="sm">Baseline</Text>
                  <InfoTip>
                    A naive "same direction as yesterday" guess over the same window. The outlook is
                    only useful if it beats this.
                  </InfoTip>
                </Group>
                <Text size="sm" fw={600} className="kv2-num">
                  {baseline.toFixed(1)}%
                </Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Difference</Text>
                <Delta value={accuracy - baseline} kind="points" decimals={1} />
              </Group>
            </Stack>
          </Panel>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Panel
            title="Rolling 20-session accuracy"
            info="Hit rate over the previous 20 sessions, plotted per session, against the baseline. Sample data."
          >
            <LineChart
              h={200}
              data={rolling}
              dataKey="session"
              series={[
                { name: "accuracy", label: "Outlook", color: "indigo.6" },
                { name: "baseline", label: "Baseline", color: "slate.4", strokeDasharray: "4 4" },
              ]}
              withDots={false}
              curveType="monotone"
              yAxisProps={{ domain: [40, 80] }}
              unit="%"
              withLegend
              tickLine="none"
              gridAxis="y"
            />
          </Panel>
        </Grid.Col>
      </Grid>
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing={12} mt={16}>
        {principles.map((item) => (
          <Group key={item.title} align="flex-start" gap={10} wrap="nowrap">
            <ThemeIcon variant="light" color="slate" size={28} radius="sm">
              {item.icon}
            </ThemeIcon>
            <div>
              <Text size="sm" fw={600}>
                {item.title}
              </Text>
              <Text size="sm" c="dimmed">
                {item.body}
              </Text>
            </div>
          </Group>
        ))}
      </SimpleGrid>
    </Section>
  );
}

function HowItWorks() {
  return (
    <Section id="how-it-works" eyebrow="How it works" title="A simpler research routine.">
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing={12}>
        {steps.map((step, index) => (
          <div key={step.title} className="kv2-panel" style={{ padding: 16 }}>
            <Stack gap={8}>
              <Text className="kv2-mono" c="indigo" fw={700} size="sm">
                {String(index + 1).padStart(2, "0")}
              </Text>
              <Text fw={600}>{step.title}</Text>
              <Text size="sm" c="dimmed">
                {step.body}
              </Text>
            </Stack>
          </div>
        ))}
      </SimpleGrid>
    </Section>
  );
}

function Delivery() {
  return (
    <Section
      eyebrow="Delivery"
      title="Read it wherever you start your day."
      description="Pick the channels you want in your account settings. The content is the same everywhere."
      muted
    >
      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing={12}>
        {channels.map((channel) => (
          <div key={channel.key} className="kv2-panel" style={{ padding: 16 }}>
            <Group gap={10} align="flex-start" wrap="nowrap">
              <ThemeIcon variant="light" color="indigo" size={28} radius="sm">
                {channelIcons[channel.key]}
              </ThemeIcon>
              <div>
                <Text size="sm" fw={600}>
                  {channel.title}
                </Text>
                <Text size="sm" c="dimmed">
                  {channel.body}
                </Text>
              </div>
            </Group>
          </div>
        ))}
      </SimpleGrid>
    </Section>
  );
}

function ClosingCta() {
  return (
    <Box component="section" py={56} style={{ borderTop: "1px solid var(--kv2-border)" }}>
      <Container size={1200}>
        <Stack align="center" gap={12} ta="center">
          <Title order={2} fz={28}>
            Your next market morning, a little clearer.
          </Title>
          <Text c="dimmed" maw={520}>
            Access is by invite while we're in preview. Already have an account? Log in to open your
            dashboard.
          </Text>
          <Group gap={8} justify="center">
            <Button
              component={AppLink}
              href="/v2/public/signup/"
              size="md"
              rightSection={<LuArrowRight size={16} />}
            >
              Request access
            </Button>
            <Button component={AppLink} href="/v2/public/login/" size="md" variant="default">
              Log in
            </Button>
          </Group>
          <Text size="xs" c="dimmed" maw={640} mt={16}>
            Kash Engine is a research tool only and does not provide investment advice or buy/sell
            recommendations. All figures on this page are illustrative sample data. Read the{" "}
            <Anchor href="#" size="xs">
              terms
            </Anchor>{" "}
            before use.
          </Text>
        </Stack>
      </Container>
    </Box>
  );
}

export function LandingPage() {
  return (
    <>
      <Hero />
      <Features />
      <TrackRecord />
      <HowItWorks />
      <Delivery />
      <ClosingCta />
    </>
  );
}
