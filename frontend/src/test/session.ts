import type { Session } from "../shared/api/generated/types.gen";

export const session: Session = {
  id: 1,
  username: "member",
  email: "member@example.test",
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
};
