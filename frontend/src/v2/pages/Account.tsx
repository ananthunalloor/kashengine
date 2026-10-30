import {
  Alert,
  Avatar,
  Button,
  CopyButton,
  Grid,
  Group,
  Modal,
  NavLink,
  PasswordInput,
  Progress,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  useMantineColorScheme,
} from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import {
  LuCheck,
  LuCopy,
  LuCreditCard,
  LuKey,
  LuLaptop,
  LuLogOut,
  LuMail,
  LuPlus,
  LuSend,
  LuShieldCheck,
  LuSlidersHorizontal,
  LuSmartphone,
  LuTrash2,
  LuTriangleAlert,
  LuUser,
} from "react-icons/lu";
import type { ReactNode } from "react";

import {
  AppLink,
  DescriptionList,
  EmptyState,
  InfoTip,
  Page,
  PageHeader,
  Panel,
  StatusBadge,
  formatDate,
  formatInr,
} from "../components";
import type { Tone } from "../components";
import {
  apiTokens,
  features,
  profile,
  sessions as initialSessions,
  subscription,
  telegramSample,
} from "../mock/account";
import type { ApiToken, Feature, PlanState } from "../mock/account";

type Section = "profile" | "security" | "notifications" | "features" | "tokens" | "preferences";

const sections: Array<{ value: Section; label: string; icon: ReactNode }> = [
  { value: "profile", label: "Profile & plan", icon: <LuUser size={14} /> },
  { value: "security", label: "Security", icon: <LuShieldCheck size={14} /> },
  { value: "notifications", label: "Notifications", icon: <LuMail size={14} /> },
  { value: "features", label: "Features", icon: <LuCreditCard size={14} /> },
  { value: "tokens", label: "API tokens", icon: <LuKey size={14} /> },
  { value: "preferences", label: "Preferences", icon: <LuSlidersHorizontal size={14} /> },
];

const planTone: Record<PlanState, Tone> = {
  none: "neutral",
  trial: "caution",
  active: "gain",
  expired: "loss",
  staff: "brand",
};
const planLabel: Record<PlanState, string> = {
  none: "No subscription",
  trial: "Trial",
  active: "Active",
  expired: "Expired",
  staff: "Staff",
};

const accessBadge: Record<Feature["access"], ReactNode> = {
  included: (
    <StatusBadge tone="gain" size="xs">
      ✓ Included
    </StatusBadge>
  ),
  "not-on-account": (
    <StatusBadge tone="neutral" size="xs">
      Not on your account
    </StatusBadge>
  ),
  locked: (
    <StatusBadge tone="caution" size="xs">
      Locked until you subscribe
    </StatusBadge>
  ),
};

const tokenTone: Record<ApiToken["state"], Tone> = {
  active: "gain",
  expired: "loss",
  revoked: "neutral",
};

function ProfileSection({ verified, onVerify }: { verified: boolean; onVerify: () => void }) {
  const [name, setName] = useState(profile.name);
  const used = 100 - (subscription.daysRemaining / 92) * 100;
  return (
    <Stack gap={16}>
      <Panel
        title="Profile"
        footer={
          <Group justify="flex-end">
            <Button
              onClick={() =>
                notifications.show({
                  title: "Profile saved",
                  message: "Your name was updated.",
                  color: "emerald",
                })
              }
            >
              Save profile
            </Button>
          </Group>
        }
      >
        <Stack gap={12}>
          <Group gap={12}>
            <Avatar color="indigo" radius="xl">
              SU
            </Avatar>
            <Stack gap={0}>
              <Text fw={600}>{name}</Text>
              <Text size="xs" c="dimmed">
                @{profile.username} · member since {formatDate(profile.memberSince)}
              </Text>
            </Stack>
          </Group>
          <Grid gutter={12}>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput
                label="Display name"
                value={name}
                onChange={(e) => setName(e.currentTarget.value)}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput
                label="Email"
                value={profile.email}
                readOnly
                rightSectionWidth={96}
                rightSection={
                  verified ? (
                    <StatusBadge tone="gain" size="xs">
                      Verified
                    </StatusBadge>
                  ) : (
                    <StatusBadge tone="caution" size="xs">
                      Unverified
                    </StatusBadge>
                  )
                }
              />
            </Grid.Col>
          </Grid>
          {!verified ? (
            <Group gap={8}>
              <Button size="xs" variant="default" onClick={onVerify}>
                Mark verified (demo)
              </Button>
            </Group>
          ) : null}
        </Stack>
      </Panel>

      <Panel
        title="Subscription"
        info="Your plan decides which features are included. Sample pricing; billing is not wired up in this preview."
        actions={
          <StatusBadge tone={planTone[subscription.state]}>
            {planLabel[subscription.state]}
          </StatusBadge>
        }
      >
        <Stack gap={12}>
          <Group justify="space-between" wrap="wrap">
            <Stack gap={2}>
              <Text fw={600}>{subscription.plan}</Text>
              <Text size="xs" c="dimmed" className="kv2-num">
                {formatInr(subscription.price, { decimals: 0 })} / {subscription.period} ·{" "}
                {subscription.currency}
              </Text>
            </Stack>
            <Button
              variant="default"
              onClick={() =>
                notifications.show({
                  title: "Billing",
                  message: "Plan changes are handled by the team (sample).",
                })
              }
            >
              Change plan
            </Button>
          </Group>
          <Stack gap={4}>
            <Group justify="space-between">
              <Text size="xs" c="dimmed">
                Current period
              </Text>
              <Text size="xs" fw={600} className="kv2-num">
                {subscription.daysRemaining} days remaining
              </Text>
            </Group>
            <Progress value={used} size={6} color="indigo" aria-label="Subscription period used" />
          </Stack>
          <DescriptionList
            items={[
              ["Started", formatDate(subscription.started)],
              ["Renews", formatDate(subscription.ends)],
              ["Questions", "Contact support@example.com"],
            ]}
          />
        </Stack>
      </Panel>
    </Stack>
  );
}

function SecuritySection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [list, setList] = useState(initialSessions);
  const mismatch = confirm.length > 0 && next !== confirm;
  const tooShort = next.length > 0 && next.length < 10;

  return (
    <Stack gap={16}>
      <Panel
        title="Change password"
        info="Use at least 10 characters. Other sessions stay signed in unless you sign them out below."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setCurrent("");
            setNext("");
            setConfirm("");
            notifications.show({
              title: "Password changed",
              message: "Use the new password next time.",
              color: "emerald",
            });
          }}
        >
          <Stack gap={10} maw={420}>
            <PasswordInput
              label="Current password"
              value={current}
              onChange={(e) => setCurrent(e.currentTarget.value)}
              required
            />
            <PasswordInput
              label="New password"
              value={next}
              onChange={(e) => setNext(e.currentTarget.value)}
              error={tooShort ? "At least 10 characters" : undefined}
              required
            />
            <PasswordInput
              label="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.currentTarget.value)}
              error={mismatch ? "Passwords don't match" : undefined}
              required
            />
            <Group>
              <Button type="submit" disabled={!current || next.length < 10 || next !== confirm}>
                Update password
              </Button>
            </Group>
          </Stack>
        </form>
      </Panel>

      <Panel
        title="Active sessions"
        info="Devices currently signed in to this account."
        flush
        actions={
          list.length > 1 ? (
            <Button
              size="xs"
              variant="subtle"
              color="red"
              onClick={() =>
                modals.openConfirmModal({
                  title: "Sign out other sessions?",
                  children: <Text size="sm">All devices except this one will be signed out.</Text>,
                  labels: { confirm: "Sign out others", cancel: "Cancel" },
                  confirmProps: { color: "red" },
                  onConfirm: () => {
                    setList((l) => l.filter((s) => s.current));
                    notifications.show({
                      title: "Signed out",
                      message: "Other sessions were signed out.",
                    });
                  },
                })
              }
            >
              Sign out others
            </Button>
          ) : null
        }
      >
        <div className="kv2-table-wrap">
          <Table>
            <Table.Tbody>
              {list.map((s) => (
                <Table.Tr key={s.id}>
                  <Table.Td>
                    <Group gap={8} wrap="nowrap">
                      {s.kind === "mobile" ? <LuSmartphone size={16} /> : <LuLaptop size={16} />}
                      <Stack gap={0}>
                        <Text size="sm">{s.device}</Text>
                        <Text size="xs" c="dimmed">
                          {s.location} · {s.lastActive}
                        </Text>
                      </Stack>
                    </Group>
                  </Table.Td>
                  <Table.Td data-align="right">
                    {s.current ? (
                      <StatusBadge tone="gain" dot size="xs">
                        This device
                      </StatusBadge>
                    ) : (
                      <Button
                        size="xs"
                        variant="subtle"
                        leftSection={<LuLogOut size={12} />}
                        onClick={() => {
                          setList((l) => l.filter((x) => x.id !== s.id));
                          notifications.show({
                            title: "Session ended",
                            message: `${s.device} was signed out.`,
                          });
                        }}
                      >
                        Sign out
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
      </Panel>
    </Stack>
  );
}

function SettingRow({
  icon,
  title,
  detail,
  control,
}: {
  icon: ReactNode;
  title: string;
  detail: ReactNode;
  control: ReactNode;
}) {
  return (
    <Group
      justify="space-between"
      wrap="nowrap"
      py={10}
      style={{ borderBottom: "1px solid var(--kv2-border)" }}
    >
      <Group gap={10} wrap="nowrap" style={{ minWidth: 0 }}>
        {icon}
        <Stack gap={0} style={{ minWidth: 0 }}>
          <Text size="sm" fw={500}>
            {title}
          </Text>
          <Text size="xs" c="dimmed">
            {detail}
          </Text>
        </Stack>
      </Group>
      {control}
    </Group>
  );
}

function NotificationsSection({ verified }: { verified: boolean }) {
  const [email, setEmail] = useState(false);
  const [telegram, setTelegram] = useState(true);
  const [alerts, setAlerts] = useState(true);
  const saved = (message: string) =>
    notifications.show({ title: "Saved", message, color: "emerald" });

  return (
    <Panel
      title="Report delivery"
      info="Switches save instantly. Manage schedule and content on the Delivery page."
      actions={
        <Button size="xs" variant="subtle" component={AppLink} href="/v2/delivery/">
          Delivery settings
        </Button>
      }
    >
      <Stack gap={0} mt={-10}>
        <SettingRow
          icon={<LuMail size={16} />}
          title={`Email reports to ${profile.email}`}
          detail={
            verified
              ? "Daily brief as an HTML email."
              : "Verify your email address to turn this on."
          }
          control={
            <Switch
              aria-label="Email reports"
              checked={email && verified}
              disabled={!verified}
              onChange={(e) => {
                setEmail(e.currentTarget.checked);
                saved(e.currentTarget.checked ? "Email reports on." : "Email reports off.");
              }}
            />
          }
        />
        <SettingRow
          icon={<LuSend size={16} />}
          title="Send reports through Telegram"
          detail={`Connected to ${telegramSample.chat} via ${telegramSample.handle}`}
          control={
            <Switch
              aria-label="Telegram reports"
              checked={telegram}
              onChange={(e) => {
                setTelegram(e.currentTarget.checked);
                saved(e.currentTarget.checked ? "Telegram reports on." : "Telegram reports off.");
              }}
            />
          }
        />
        <SettingRow
          icon={<LuTriangleAlert size={16} />}
          title="Account alerts"
          detail="Subscription ending, new sign-ins and token expiry."
          control={
            <Switch
              aria-label="Account alerts"
              checked={alerts}
              onChange={(e) => {
                setAlerts(e.currentTarget.checked);
                saved(e.currentTarget.checked ? "Account alerts on." : "Account alerts off.");
              }}
            />
          }
        />
      </Stack>
    </Panel>
  );
}

function FeaturesSection() {
  return (
    <Panel
      title="Features"
      info="What your current plan includes. Locked features unlock with an active subscription."
      flush
    >
      <div className="kv2-table-wrap">
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Feature</Table.Th>
              <Table.Th>Access</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {features.map((f) => (
              <Table.Tr key={f.name}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {f.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {f.help}
                  </Text>
                </Table.Td>
                <Table.Td>{accessBadge[f.access]}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </div>
    </Panel>
  );
}

function TokensSection() {
  const [tokens, setTokens] = useState<ApiToken[]>(apiTokens);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState<string | null>("90");
  const [newToken, setNewToken] = useState<string | null>(null);

  const create = () => {
    const suffix = Math.random().toString(16).slice(2, 6);
    const secret = `kash_sample_${Math.random().toString(36).slice(2, 14)}${suffix}`;
    const ends = new Date(Date.UTC(2026, 0, 12 + Number(expiry ?? 90))).toISOString().slice(0, 10);
    setTokens((t) => [
      {
        id: `t${Date.now()}`,
        name: name.trim(),
        suffix,
        created: "2026-01-12",
        lastUsed: null,
        ends,
        state: "active",
      },
      ...t,
    ]);
    setNewToken(secret);
    setName("");
  };

  const revoke = (token: ApiToken) =>
    modals.openConfirmModal({
      title: `Revoke “${token.name}”?`,
      children: (
        <Text size="sm">
          Scripts using this token will stop working immediately. This can't be undone.
        </Text>
      ),
      labels: { confirm: "Revoke token", cancel: "Cancel" },
      confirmProps: { color: "red" },
      onConfirm: () => {
        setTokens((t) => t.map((x) => (x.id === token.id ? { ...x, state: "revoked" } : x)));
        notifications.show({
          title: "Token revoked",
          message: `${token.name} can no longer be used.`,
        });
      },
    });

  return (
    <Panel
      title="API tokens"
      info="Personal tokens give read-only API access with your account's permissions. Treat them like passwords."
      flush
      actions={
        <Button size="xs" leftSection={<LuPlus size={14} />} onClick={() => setCreateOpen(true)}>
          New token
        </Button>
      }
      footer={
        <Text size="xs" c="dimmed">
          Send the token in the <span className="kv2-mono">Authorization: Bearer …</span> header.
          See the sample API docs.
        </Text>
      }
    >
      {tokens.length === 0 ? (
        <EmptyState
          title="No tokens yet"
          description="Create a token to call the API from scripts or notebooks."
        />
      ) : (
        <div className="kv2-table-wrap">
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Token</Table.Th>
                <Table.Th visibleFrom="md">Last used</Table.Th>
                <Table.Th visibleFrom="md">Ends</Table.Th>
                <Table.Th>State</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tokens.map((t) => (
                <Table.Tr key={t.id}>
                  <Table.Td>{t.name}</Table.Td>
                  <Table.Td className="kv2-mono">kash_••••{t.suffix}</Table.Td>
                  <Table.Td visibleFrom="md">
                    {t.lastUsed ? formatDate(t.lastUsed) : "Never"}
                  </Table.Td>
                  <Table.Td visibleFrom="md">{formatDate(t.ends)}</Table.Td>
                  <Table.Td>
                    <StatusBadge tone={tokenTone[t.state]} size="xs">
                      {t.state[0].toUpperCase() + t.state.slice(1)}
                    </StatusBadge>
                  </Table.Td>
                  <Table.Td data-align="right">
                    {t.state === "active" ? (
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<LuTrash2 size={12} />}
                        onClick={() => revoke(t)}
                      >
                        Revoke
                      </Button>
                    ) : null}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
      )}

      <Modal
        opened={createOpen}
        onClose={() => {
          setCreateOpen(false);
          setNewToken(null);
        }}
        title={newToken ? "Copy your new token" : "Create API token"}
      >
        {newToken ? (
          <Stack gap={12}>
            <Alert color="amber" icon={<LuTriangleAlert size={16} />}>
              Copy this token now. It won't be shown again.
            </Alert>
            <Group gap={8} wrap="nowrap">
              <TextInput
                readOnly
                value={newToken}
                className="kv2-mono"
                style={{ flex: 1 }}
                aria-label="New token"
              />
              <CopyButton value={newToken}>
                {({ copied, copy }) => (
                  <Button
                    variant={copied ? "light" : "default"}
                    color={copied ? "emerald" : undefined}
                    leftSection={copied ? <LuCheck size={14} /> : <LuCopy size={14} />}
                    onClick={copy}
                  >
                    {copied ? "Copied" : "Copy"}
                  </Button>
                )}
              </CopyButton>
            </Group>
            <Group justify="flex-end">
              <Button
                onClick={() => {
                  setCreateOpen(false);
                  setNewToken(null);
                }}
              >
                Done
              </Button>
            </Group>
          </Stack>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) create();
            }}
          >
            <Stack gap={12}>
              <TextInput
                label="Token name"
                description="So you can recognise it later, e.g. “Research notebook”."
                maxLength={60}
                value={name}
                onChange={(e) => setName(e.currentTarget.value)}
                data-autofocus
                required
              />
              <Select
                label="Expires after"
                data={[
                  { value: "30", label: "30 days" },
                  { value: "90", label: "90 days" },
                  { value: "365", label: "1 year" },
                ]}
                value={expiry}
                onChange={setExpiry}
                allowDeselect={false}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!name.trim()}>
                  Make token
                </Button>
              </Group>
            </Stack>
          </form>
        )}
      </Modal>
    </Panel>
  );
}

function PreferencesSection() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const [density, setDensity] = useState("compact");
  const [landing, setLanding] = useState<string | null>("today");

  return (
    <Panel
      title="Preferences"
      info="Saved on this device in the real app. In this preview only the theme takes effect."
    >
      <Stack gap={16} maw={480}>
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Theme
          </Text>
          <SegmentedControl
            value={colorScheme}
            onChange={(v) => setColorScheme(v as "light" | "dark" | "auto")}
            data={[
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
              { value: "auto", label: "System" },
            ]}
          />
        </Stack>
        <Stack gap={4}>
          <Group gap={4}>
            <Text size="sm" fw={500}>
              Density
            </Text>
            <InfoTip>
              Compact fits more rows on screen; comfortable adds spacing for touch screens.
            </InfoTip>
          </Group>
          <SegmentedControl
            value={density}
            onChange={(v) => {
              setDensity(v);
              notifications.show({
                title: "Density saved",
                message: `Tables will use ${v} spacing.`,
              });
            }}
            data={[
              { value: "compact", label: "Compact" },
              { value: "comfortable", label: "Comfortable" },
            ]}
          />
        </Stack>
        <Select
          label="Start page"
          description="Where you land after signing in."
          data={[
            { value: "today", label: "Today" },
            { value: "markets", label: "Markets" },
            { value: "reports", label: "Reports" },
          ]}
          value={landing}
          onChange={setLanding}
          allowDeselect={false}
        />
        <TextInput
          label="Time zone"
          value={profile.timezone}
          readOnly
          description="Times are always shown in IST."
        />
      </Stack>
    </Panel>
  );
}

export function AccountPage() {
  const [section, setSection] = useState<Section>("profile");
  const [verified, setVerified] = useState(profile.emailVerified);
  const wide = useMediaQuery("(min-width: 62em)");

  const content: Record<Section, ReactNode> = {
    profile: <ProfileSection verified={verified} onVerify={() => setVerified(true)} />,
    security: <SecuritySection />,
    notifications: <NotificationsSection verified={verified} />,
    features: <FeaturesSection />,
    tokens: <TokensSection />,
    preferences: <PreferencesSection />,
  };

  return (
    <Page>
      <PageHeader
        title="Your account"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "Account" }]}
        description={`@${profile.username} · ${profile.email}`}
        meta={
          <StatusBadge tone={planTone[subscription.state]}>
            {planLabel[subscription.state]}
          </StatusBadge>
        }
      />

      <Stack gap={16}>
        {!verified ? (
          <Alert color="amber" icon={<LuMail size={16} />} title="Verify your email address">
            <Group justify="space-between" gap={8} wrap="wrap">
              <Text size="sm">Email reports stay off until {profile.email} is verified.</Text>
              <Button
                size="xs"
                variant="default"
                onClick={() =>
                  notifications.show({
                    title: "Verification email sent",
                    message: `Check ${profile.email} (sample).`,
                  })
                }
              >
                Send verification email
              </Button>
            </Group>
          </Alert>
        ) : null}

        {wide ? (
          <Grid gutter={16}>
            <Grid.Col span={3}>
              <nav aria-label="Account sections" className="kv2-panel" style={{ padding: 4 }}>
                {sections.map((s) => (
                  <NavLink
                    key={s.value}
                    label={s.label}
                    leftSection={s.icon}
                    active={section === s.value}
                    onClick={() => setSection(s.value)}
                  />
                ))}
              </nav>
            </Grid.Col>
            <Grid.Col span={9}>{content[section]}</Grid.Col>
          </Grid>
        ) : (
          <Tabs value={section} onChange={(v) => v && setSection(v as Section)}>
            <Tabs.List style={{ overflowX: "auto", flexWrap: "nowrap" }}>
              {sections.map((s) => (
                <Tabs.Tab key={s.value} value={s.value} leftSection={s.icon}>
                  {s.label}
                </Tabs.Tab>
              ))}
            </Tabs.List>
            <div style={{ paddingTop: 16 }}>{content[section]}</div>
          </Tabs>
        )}
      </Stack>
    </Page>
  );
}
