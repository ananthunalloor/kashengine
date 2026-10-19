import { useEffect, useId, useRef, useState } from "react";
import { LuCircleUserRound, LuLogOut, LuShieldCheck, LuX } from "react-icons/lu";

import { csrfToken } from "../api/client";
import type { Session } from "../api/generated/types.gen";

const subscriptionLabels: Record<Session["subscription_state"], string> = {
  trial: "Trial",
  active: "Active subscription",
  expired: "Subscription expired",
  none: "No subscription",
  staff: "Subscription exempt",
};

export function AccountMenu({ session, pathname }: { session: Session; pathname: string }) {
  const [opened, setOpened] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const accountLink = useRef<HTMLAnchorElement>(null);
  const id = useId();
  const token = csrfToken();
  const role = session.is_superuser ? "Superuser" : session.is_staff ? "Staff" : "Member";
  const initials = Array.from(session.username.trim()).slice(0, 2).join("").toUpperCase() || "?";

  useEffect(() => setOpened(false), [pathname]);
  useEffect(() => {
    if (!opened) return;
    accountLink.current?.focus();
    function dismiss(event: PointerEvent | FocusEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpened(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpened(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("focusin", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("focusin", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [opened]);

  return (
    <div className="account-menu" ref={root}>
      <button
        type="button"
        className="account-avatar account-menu-trigger"
        ref={trigger}
        aria-label={`Account menu for ${session.username}`}
        aria-expanded={opened}
        aria-controls={opened ? id : undefined}
        aria-haspopup="dialog"
        title="Your account"
        onClick={() => setOpened((value) => !value)}
      >
        <span aria-hidden="true">{initials}</span>
      </button>
      {opened && (
        <section id={id} role="dialog" aria-label="Your account" className="account-popover">
          <div className="account-popover-identity">
            <span className="account-avatar" aria-hidden="true">
              {initials}
            </span>
            <div>
              <strong>{session.username}</strong>
              <p>{session.email || "Email not set"}</p>
            </div>
            <button
              type="button"
              className="header-icon-button"
              aria-label="Close account menu"
              onClick={() => {
                setOpened(false);
                trigger.current?.focus();
              }}
            >
              <LuX aria-hidden="true" />
            </button>
          </div>
          <dl className="account-popover-details">
            <div>
              <dt>Role</dt>
              <dd>
                <LuShieldCheck aria-hidden="true" /> {role}
              </dd>
            </div>
            <div>
              <dt>Subscription</dt>
              <dd>{subscriptionLabels[session.subscription_state]}</dd>
            </div>
          </dl>
          {!session.subscription_required && session.subscription_state !== "staff" && (
            <p className="account-popover-note">A subscription is not currently required.</p>
          )}
          {session.notice && <p className="account-popover-note">{session.notice}</p>}
          <div className="account-popover-actions">
            <a href="/account/" ref={accountLink} onClick={() => setOpened(false)}>
              <LuCircleUserRound aria-hidden="true" /> Account details
            </a>
            <form action={session.logout_url} method="post">
              <input type="hidden" name="csrfmiddlewaretoken" value={token ?? ""} />
              <input type="hidden" name="next" value="/login/" />
              <button type="submit" disabled={!token}>
                <LuLogOut aria-hidden="true" /> Log out
              </button>
            </form>
          </div>
          {!token && (
            <p role="alert" className="account-popover-note">
              Reload the page to enable secure logout.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
