import { useState } from "react";
import { useComputedColorScheme, useMantineColorScheme } from "@mantine/core";
import {
  LuArrowRight,
  LuBuilding2,
  LuChartNoAxesCombined,
  LuCheck,
  LuFileText,
  LuMoon,
  LuNewspaper,
  LuSend,
  LuShieldCheck,
  LuSparkles,
  LuSun,
} from "react-icons/lu";
import { z } from "zod";

import { usePageTitle } from "../../shared/ui/usePageTitle";
import { PageNotFound } from "../../shared/ui/PageNotFound";

export const publicPageSchema = z.object({
  page: z.enum(["landing", "login", "access", "lockout", "not-found"]),
  authenticated: z.boolean(),
  csrf: z.string(),
  next: z.string().default(""),
  invalid: z.boolean().default(false),
  feature: z.string().default("This feature"),
  minutes: z.number().nullable().default(null),
});

type PublicData = z.infer<typeof publicPageSchema>;

const capabilities = [
  {
    path: "news",
    title: "News with a point of view",
    icon: LuNewspaper,
    text: "Follow financial headlines with sentiment scores and a reason behind each signal. Less scrolling, more understanding.",
    detail:
      "Search stories and filter by source or sentiment. See positive and negative coverage together, with the model's explanation for each scored article.",
    tags: ["Scored sentiment", "Source filters"],
  },
  {
    path: "markets",
    title: "A more informed outlook",
    icon: LuChartNoAxesCombined,
    text: "Connect news sentiment with global market cues for a next-session outlook on the Nifty 50.",
    detail:
      "Review signal strength, prediction history, index quotes, and measured accuracy against a baseline. Signal strength is not a probability of being right.",
    tags: ["Market direction", "Track record"],
  },
  {
    path: "ipos",
    title: "IPOs, beyond the buzz",
    icon: LuShieldCheck,
    text: "Keep upcoming and open issues in view, with key facts and scoring signals to guide your own research.",
    detail:
      "Filter issues by status, verdict, or category. Examine dates, available facts, scoring inputs, and notes. GMP is unofficial, not a guarantee.",
    tags: ["Issue calendar", "Score breakdowns"],
  },
  {
    path: "companies",
    title: "Know the companies",
    icon: LuBuilding2,
    text: "Look up company data in one searchable directory. Add business context to the names in your news feed.",
    detail:
      "Review available financial data collected from Screener.in. Data availability depends on the configured collection jobs.",
    tags: ["Company search", "Fundamentals"],
  },
  {
    path: "reports",
    title: "Your daily market brief",
    icon: LuFileText,
    text: "Bring the outlook, important stories, and IPO watchlist together in one readable report. Revisit any day.",
    detail:
      "Browse past reports by date and move between daily editions, bringing together available news, market signals, and IPO information.",
    tags: ["Daily digest", "Report archive"],
  },
  {
    path: "delivery",
    title: "From the engine to you",
    icon: LuSend,
    text: "Get the daily report through configured Telegram delivery, and check whether each send made it through.",
    detail:
      "Review send attempts, delivery status, and errors. Telegram destinations and scheduled sending are configured by your administrator.",
    tags: ["Telegram delivery", "Delivery history"],
  },
];

function Brand() {
  return (
    <a href="/" className="app-brand" aria-label="Kash Engine home">
      <span className="app-brand-mark" aria-hidden="true">
        k.
      </span>
      <span>
        kash<span className="app-brand-light">engine</span>
      </span>
    </a>
  );
}

export function Landing({ authenticated }: Pick<PublicData, "authenticated">) {
  const destination = authenticated ? "/dashboard/" : "/login/";
  return (
    <>
      <section className="public-hero" aria-labelledby="hero-title">
        <div>
          <p className="app-eyebrow">
            <LuSparkles aria-hidden="true" /> A clearer view of Indian markets
          </p>
          <h1 id="hero-title">
            Less noise.
            <br />
            More <span>perspective.</span>
          </h1>
          <p className="public-lead">
            From the headlines to the opening bell. Bring market news, sentiment, and IPO research
            together in one thoughtful daily view.
          </p>
          <div className="public-actions">
            <a className="public-button" href={destination}>
              Explore your dashboard <LuArrowRight aria-hidden="true" />
            </a>
            <a href="#capabilities">See what's inside</a>
          </div>
          <p className="public-notes">
            <span>
              <LuCheck aria-hidden="true" /> Built for Indian markets
            </span>
            <span>
              <LuCheck aria-hidden="true" /> Powered by a local AI model
            </span>
          </p>
        </div>
        <section className="public-brief" aria-labelledby="brief-title">
          <div className="public-brief-top">
            <span className="app-eyebrow">Your daily perspective</span>
            <span>Illustrative preview</span>
          </div>
          <h2 id="brief-title">
            A little context.
            <br />A clearer morning.
          </h2>
          <p className="public-brief-top">
            Market outlook <span className="public-positive">Positive signal</span>
          </p>
          <strong>Nifty 50</strong>
          <svg
            className="public-chart"
            viewBox="0 0 400 120"
            role="img"
            aria-label="Illustrative rising trend, not live market data"
          >
            <path className="public-chart-grid" d="M0 25H400M0 65H400M0 105H400" />
            <path
              className="public-chart-line"
              d="M0 100 25 90 45 95 65 70 85 80 110 62 135 70 160 50 185 60 210 35 235 45 260 25 285 35 310 15 335 25 360 12 385 20 400 5"
            />
          </svg>
          <div className="public-brief-story">
            <LuNewspaper aria-hidden="true" />
            <div>
              <strong>The stories behind the signal</strong>
              <p>Scored news. Reasons included.</p>
            </div>
          </div>
          <p className="public-brief-top">
            <span>News, outlook &amp; IPOs</span>
            <span>One daily report</span>
          </p>
          <p className="public-telegram">
            <LuSend aria-hidden="true" /> Your morning, simplified. Daily reports via Telegram.
          </p>
        </section>
      </section>
      <section id="capabilities" className="public-section" aria-labelledby="capabilities-title">
        <p className="app-eyebrow">Your research, connected</p>
        <h2 id="capabilities-title">One engine. The whole picture.</h2>
        <p>Go beyond the headline. Find the context that helps you ask better questions.</p>
        <div className="public-capabilities">
          {capabilities.map(({ path, title, icon: Icon, text, detail, tags }) => (
            <article className="public-card" key={path}>
              <Icon className="public-capability-icon" aria-hidden="true" />
              <h3>{title}</h3>
              <p>{text}</p>
              <div className="public-tags">
                {tags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
              <details>
                <summary>Explore {path} capabilities</summary>
                <p>{detail}</p>
                <a href={`/${path}/`}>
                  Open {path} <LuArrowRight aria-hidden="true" />
                </a>
              </details>
            </article>
          ))}
        </div>
        <aside className="public-api">
          <p>
            <strong>Prefer to build your own view?</strong> Read the data through our versioned,
            read-only REST API.
          </p>
          <a href="/docs/">
            Explore API docs <LuArrowRight aria-hidden="true" />
          </a>
        </aside>
      </section>
      <section id="how-it-works" className="public-section" aria-labelledby="workflow-title">
        <p className="app-eyebrow">From information to perspective</p>
        <h2 id="workflow-title">A simpler research routine.</h2>
        <p>The groundwork happens in the background. You start with the context.</p>
        <div className="public-workflow">
          {[
            [
              "Collect the signals",
              "News feeds, company data, IPO information, and market quotes come together.",
            ],
            [
              "Connect the context",
              "A local language model scores news sentiment. Rules combine it with market cues.",
            ],
            [
              "Start with the big picture",
              "Read the daily brief, explore the details, and make your own informed decisions.",
            ],
          ].map(([title, text], index) => (
            <article key={title}>
              <span className="app-eyebrow">0{index + 1}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section
        id="principles"
        className="public-section public-principles"
        aria-labelledby="principles-title"
      >
        <div>
          <p className="app-eyebrow">Perspective, not promises</p>
          <h2 id="principles-title">
            Research tools.
            <br />
            Not a crystal ball.
          </h2>
        </div>
        <div>
          <p>
            Markets are uncertain. Your tools should be honest about that. Kash Engine shows the
            reasoning, tracks the outcomes, and keeps the limitations in view.
          </p>
          <ul>
            {[
              "Explanations alongside signals",
              "Accuracy measured against a baseline",
              "Your judgment stays in the driver's seat",
            ].map((text) => (
              <li key={text}>
                <LuCheck aria-hidden="true" />
                {text}
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section className="public-closing">
        <div>
          <p className="app-eyebrow">Make room for the big picture</p>
          <h2>
            Your next market morning,
            <br />a little clearer.
          </h2>
          <p>All your research signals. One place to begin.</p>
        </div>
        <a className="public-button" href={destination}>
          {authenticated ? "Open your dashboard" : "Log in to Kash Engine"}
          <LuArrowRight aria-hidden="true" />
        </a>
      </section>
    </>
  );
}

function Login({ data }: { data: PublicData }) {
  const [pending, setPending] = useState(false);
  return (
    <section className="public-auth" aria-labelledby="login-title">
      <h1 id="login-title">Log in</h1>
      <p>
        Use the account that you made with <code>createsuperuser</code>.
      </p>
      {data.invalid && (
        <p className="public-error" role="alert">
          The user name or the password is not correct. Try again.
        </p>
      )}
      <form method="post" action="/login/" onSubmit={() => setPending(true)} aria-busy={pending}>
        <input type="hidden" name="csrfmiddlewaretoken" value={data.csrf} />
        <input type="hidden" name="next" value={data.next} />
        <label htmlFor="username">User name</label>
        <input id="username" name="username" autoComplete="username" required maxLength={150} />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <button className="public-button" disabled={pending} type="submit">
          {pending ? "Logging in..." : "Log in"}
          <LuArrowRight aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export function PublicPage({ data }: { data: PublicData }) {
  const { setColorScheme } = useMantineColorScheme({ keepTransitions: true });
  const theme = useComputedColorScheme("light", { getInitialValueInEffect: true });
  const title =
    data.page === "landing"
      ? "Less noise. More perspective."
      : data.page === "login"
        ? "Log in"
        : data.page === "access"
          ? "Not on your account"
          : data.page === "not-found"
            ? "Page not found"
            : "Too many tries";
  usePageTitle(title);
  return (
    <div className="public-site">
      <header className="public-header">
        <Brand />
        {data.page === "landing" && (
          <nav aria-label="Main navigation">
            <a href="#capabilities">Capabilities</a>
            <a href="#how-it-works">How it works</a>
            <a href="#principles">Our approach</a>
          </nav>
        )}
        <div className="public-actions">
          <button
            type="button"
            className="header-icon-button"
            aria-label="Toggle color scheme"
            onClick={() => setColorScheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <LuSun aria-hidden="true" /> : <LuMoon aria-hidden="true" />}
          </button>
          {data.page !== "login" && (
            <a className="public-header-link" href={data.authenticated ? "/dashboard/" : "/login/"}>
              {data.authenticated ? "Open dashboard" : "Log in"}
              <LuArrowRight aria-hidden="true" />
            </a>
          )}
        </div>
      </header>
      <main id="main">
        {data.page === "landing" ? (
          <Landing authenticated={data.authenticated} />
        ) : data.page === "login" ? (
          <Login data={data} />
        ) : data.page === "not-found" ? (
          <PageNotFound />
        ) : (
          <section className="public-auth" aria-labelledby="status-title">
            <h1 id="status-title">{title}</h1>
            {data.page === "access" ? (
              <>
                <p>
                  {data.feature} is not on for your account. See the <a href="/account/">Account</a>{" "}
                  page to learn what you have, or ask the admin.
                </p>
                <a href="/dashboard/">Back to Today</a>
              </>
            ) : (
              <>
                <p>
                  There were too many failed logins from this address.{" "}
                  {data.minutes
                    ? `Try again in about ${data.minutes} minute${data.minutes === 1 ? "" : "s"}.`
                    : "Ask an admin to unlock the address."}
                </p>
                <a href="/login/">Back to the login</a>
              </>
            )}
          </section>
        )}
      </main>
      <footer className="public-footer">
        <Brand />
        <p>A little less noise. A lot more context.</p>
        <p>
          Not financial advice. Predictions can be wrong. GMP is unofficial. Always do your own
          research.
        </p>
        <a href="/docs/">Documentation</a>
      </footer>
    </div>
  );
}
