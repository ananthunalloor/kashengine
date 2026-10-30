import {
  Anchor,
  Box,
  Button,
  Checkbox,
  Group,
  PasswordInput,
  Progress,
  Stack,
  Tabs,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { LuKeyRound, LuLock, LuMail, LuShieldCheck } from "react-icons/lu";

import { AppLink, InfoTip } from "../components";

type Mode = "login" | "signup";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function showPreviewNotice() {
  notifications.show({
    title: "Preview only",
    message: "Preview only — no account created and nothing was sent.",
    color: "indigo",
  });
}

function AuthCard({ mode, children }: { mode: Mode; children: ReactNode }) {
  const navigate = useNavigate();
  return (
    <Box px={16} py={{ base: 32, md: 56 }}>
      <Stack gap={16} maw={400} mx="auto">
        <Stack gap={4} align="center" ta="center">
          <span className="kv2-logo">
            <span className="kv2-logo-mark">k</span>
            <span>kashengine</span>
          </span>
          <Text size="sm" c="dimmed">
            {mode === "login"
              ? "Welcome back. Log in to open your dashboard."
              : "Create an account with your invite code."}
          </Text>
        </Stack>
        <div className="kv2-panel">
          <Tabs
            value={mode}
            onChange={(value) => {
              if (value && value !== mode)
                void navigate({
                  to: value === "login" ? "/v2/public/login/" : "/v2/public/signup/",
                });
            }}
          >
            <Tabs.List grow>
              <Tabs.Tab value="login">Log in</Tabs.Tab>
              <Tabs.Tab value="signup">Sign up</Tabs.Tab>
            </Tabs.List>
          </Tabs>
          <Box p={20}>{children}</Box>
        </div>
        <Group gap={6} justify="center" wrap="nowrap">
          <LuShieldCheck size={14} color="var(--kv2-text-muted)" />
          <Text size="xs" c="dimmed">
            Research only. Kash Engine does not give investment advice or buy/sell recommendations.
          </Text>
        </Group>
      </Stack>
    </Box>
  );
}

export function MockLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [pending, setPending] = useState(false);

  const validate = () => {
    const next: typeof errors = {};
    if (!email.trim()) next.email = "Enter your email.";
    else if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setPending(true);
    window.setTimeout(() => {
      setPending(false);
      showPreviewNotice();
    }, 600);
  };

  return (
    <AuthCard mode="login">
      <form onSubmit={onSubmit} noValidate>
        <Stack gap={12}>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            leftSection={<LuMail size={14} />}
            value={email}
            onChange={(event) => setEmail(event.currentTarget.value)}
            error={errors.email}
            required
          />
          <Stack gap={4}>
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              leftSection={<LuLock size={14} />}
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              error={errors.password}
              required
            />
            <Group justify="flex-end">
              <Anchor href="#" size="xs" onClick={(event) => event.preventDefault()}>
                Forgot password?
              </Anchor>
            </Group>
          </Stack>
          <Button type="submit" fullWidth loading={pending}>
            Log in
          </Button>
          <Text size="xs" c="dimmed" ta="center">
            Need an account?{" "}
            <Anchor component={AppLink} href="/v2/public/signup/" size="xs">
              Sign up with an invite code
            </Anchor>
          </Text>
        </Stack>
      </form>
    </AuthCard>
  );
}

function passwordStrength(value: string) {
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  if (score <= 1) return { score, label: "Weak", color: "red" };
  if (score <= 3) return { score, label: "Fair", color: "amber" };
  return { score, label: "Strong", color: "emerald" };
}

type SignupErrors = { email?: string; invite?: string; password?: string; terms?: string };

export function MockSignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [invite, setInvite] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState<SignupErrors>({});
  const [pending, setPending] = useState(false);
  const strength = passwordStrength(password);

  const validate = () => {
    const next: SignupErrors = {};
    if (!email.trim()) next.email = "Enter your email.";
    else if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email address.";
    if (!invite.trim()) next.invite = "An invite code is required.";
    else if (invite.trim().length < 6) next.invite = "Invite codes are at least 6 characters.";
    if (!password) next.password = "Choose a password.";
    else if (password.length < 8) next.password = "Use at least 8 characters.";
    if (!terms) next.terms = "You need to accept the Terms and Privacy Notice.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!validate()) return;
    setPending(true);
    window.setTimeout(() => {
      setPending(false);
      showPreviewNotice();
      void navigate({ to: "/v2/public/signup-complete/" });
    }, 600);
  };

  return (
    <AuthCard mode="signup">
      <form onSubmit={onSubmit} noValidate>
        <Stack gap={12}>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            leftSection={<LuMail size={14} />}
            value={email}
            onChange={(event) => setEmail(event.currentTarget.value)}
            error={errors.email}
            required
          />
          <TextInput
            label={
              <Group gap={4} component="span" display="inline-flex">
                Invite code
                <InfoTip label="About invite codes">
                  Access is invite-only during the preview. Each code works once and may expire.
                </InfoTip>
              </Group>
            }

            description="Ask the admin for an invite."
            placeholder="e.g. SAMPLE-1234"
            autoComplete="off"
            leftSection={<LuKeyRound size={14} />}
            value={invite}
            onChange={(event) => setInvite(event.currentTarget.value)}
            error={errors.invite}
            classNames={{ input: "kv2-mono" }}
            required
          />
          <Stack gap={6}>
            <PasswordInput
              label="Password"
              autoComplete="new-password"
              leftSection={<LuLock size={14} />}
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              error={errors.password}
              required
            />
            {password ? (
              <Stack gap={4}>
                <Progress
                  value={(strength.score / 5) * 100}
                  color={strength.color}
                  size="xs"
                  aria-label="Password strength"
                />
                <Text size="xs" c="dimmed">
                  Strength: <b>{strength.label}</b> · use 12+ characters with a mix of letters,
                  numbers and symbols.
                </Text>
              </Stack>
            ) : (
              <Text size="xs" c="dimmed">
                At least 8 characters.
              </Text>
            )}
          </Stack>
          <Checkbox
            checked={terms}
            onChange={(event) => setTerms(event.currentTarget.checked)}
            error={errors.terms}
            label={
              <>
                I agree to the{" "}
                <Anchor component={AppLink} href="/v2/public/legal/" size="sm">
                  Terms
                </Anchor>{" "}
                and{" "}
                <Anchor component={AppLink} href="/v2/public/legal/" size="sm">
                  Privacy Notice
                </Anchor>
              </>
            }
          />
          <Button type="submit" fullWidth loading={pending}>
            Create account
          </Button>
          <Text size="xs" c="dimmed" ta="center">
            Already have an account?{" "}
            <Anchor component={AppLink} href="/v2/public/login/" size="xs">
              Log in
            </Anchor>
          </Text>
        </Stack>
      </form>
    </AuthCard>
  );
}

export { LoginPage, SignupPage } from "./DataDriven";
