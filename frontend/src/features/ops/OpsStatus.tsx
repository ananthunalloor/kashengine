import type { ReactNode } from "react";
import type { IconType } from "react-icons";
import { Alert } from "@mantine/core";
import { LuCircleCheck, LuCircleX, LuInfo, LuTriangleAlert } from "react-icons/lu";
import type { OpsMessage } from "../../shared/api/generated/types.gen";

type Tone = "positive" | "negative" | "warning" | "neutral";

const icons = {
  positive: LuCircleCheck,
  negative: LuCircleX,
  warning: LuTriangleAlert,
  neutral: LuInfo,
};

export function OpsStatus({
  tone,
  children,
  icon,
}: {
  tone: Tone;
  children: ReactNode;
  icon?: IconType;
}) {
  const Icon = icon ?? icons[tone];
  return (
    <span className={`ops-status ops-tone-${tone}`}>
      <Icon aria-hidden="true" />
      {children}
    </span>
  );
}

export function OpsNotice({ messages }: { messages: OpsMessage[] }) {
  return (
    <div role={messages.some((message) => message.level === "error") ? "alert" : "status"}>
      {messages.map((message, index) => {
        const tone =
          message.level === "error"
            ? "negative"
            : message.level === "warning"
              ? "warning"
              : message.level === "success"
                ? "positive"
                : "neutral";
        return (
          <Alert
            key={index}
            color={
              tone === "negative"
                ? "red"
                : tone === "warning"
                  ? "yellow"
                  : tone === "positive"
                    ? "green"
                    : "blue"
            }
            title={<OpsStatus tone={tone}>{message.level}</OpsStatus>}
          >
            {message.text}
          </Alert>
        );
      })}
    </div>
  );
}
