import type { Session } from "../shared/api/generated/types.gen";

export const session: Session = {
  id: 1,
  username: "member",
  email: "member@example.test",
  email_verified: true,
  is_staff: false,
  is_superuser: false,
  features: ["reports"],
  subscription_required: false,
  subscription_ok: true,
  subscription_state: "trial",
  notice: "",
  navigation: [
    { label: "Today", url: "/dashboard/" },
    { label: "Reports", url: "/reports/" },
    { label: "Account", url: "/account/" },
  ],
  logout_url: "/logout/",
  market_calendar: {
    year: 2026,
    as_of: "2026-10-23T04:30:00Z",
    next_change_at: "2099-10-23T10:00:00Z",
    is_open: true,
    status_key: "2026-10-23:open",
    reason: "Regular trading session",
    special_reason: "",
    source_url: "https://www.nseindia.com/resources/exchange-communication-holidays",
    days: [],
  },
};
