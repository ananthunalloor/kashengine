# Kash Engine — UI Redesign Brief

A handoff for the UI designer. It covers every screen in the product: what it is for, who sees it, what is on it today, and what the redesign should do.

**Goals**

- **More compact.** Show more on one screen with less scrolling. The current UI is spacious, uses large type and long single-column pages.
- **Keep the colours.** Keep the violet/indigo brand, green for gains, red for losses and amber for caution. Use the Tailwind palette steps listed in [Colour tokens](#2-colour-tokens-tailwind).
- **Modern and functional.** Every element should help the user make a decision or move on. Remove repeated explanations, keep disclaimers short, and keep one obvious next action.
- **Use Mantine UI (v8).** Use Mantine components only. The app already uses `@mantine/core` and `@mantine/dates` 8.x. See [Component library](#4-component-library-mantine-v8).

---

## 1. Product in one paragraph

Kash Engine is a research tool for the Indian stock market (NSE/BSE). Every morning it collects news and scores its sentiment with a local AI model. It also tracks global markets and predicts the direction of the Nifty 50, then measures how often it was right. It scores IPOs and keeps a company directory with fundamentals, prices and charts. A daily report goes out by email or Telegram. There is also a staff-only **Ops** area for running jobs, managing users and configuring the system. **It is not a trading app.** It gives no buy/sell advice, so the UI must never look like a brokerage terminal that issues signals.

### Users and access

| Who | What they see |
|---|---|
| Visitor (signed out) | Landing, Log in, Sign up, Legal, 404 |
| Signed-in, email not verified | Only the Account page; other pages redirect there |
| Signed-in, verified | Today + the **features** turned on for them (Reports, News, IPOs, Markets, Companies, Delivery) + Account |
| Subscription expired | Locked out of features; can still open Account and revoke API tokens |
| Staff | Everything + **Ops** area (read-only for most actions) |
| Superuser | Staff + can make changes in Ops + Backups page |

Admins turn features on or off per user, so **navigation, dashboard sections and cross-links must cope with any feature being absent**. Hide what is unavailable. Do not show dead links.

### Formatting conventions (keep)

- Currency: INR, Indian grouping (₹1,23,456.78), max 2 decimals.
- Times: always IST, e.g. `29 Oct 2026, 05:11 IST`.
- Change values: green with ▲ for up, red with ▼ for down, neutral grey for flat. **Never rely on colour alone.** Always pair it with an arrow or sign.
- Scores: **Signal strength 1.0–10.0** (not a probability), **news/global neutral = 5.5**, **sentiment −1 to +1**, **relevance 0 to 1**, **IPO score −1 to +1**.

---

## 2. Colour tokens (Tailwind)

These are the current brand colours mapped to the nearest Tailwind step. Use the Tailwind step, so the redesign stays on the Tailwind palette and looks like today's app.

### Light theme

| Role | Current | Tailwind | Use |
|---|---|---|---|
| Primary | `#6654d9` | **indigo-600** `#4f46e5` | Buttons, active nav, links, focus ring |
| Primary hover | `#5542c8` | **indigo-700** `#4338ca` | |
| Primary soft | `#f4f1fe` | **violet-50** `#f5f3ff` | Active nav background, selected rows, chips |
| Text | `#202436` | **slate-800** `#1e293b` | Body/headings |
| Text muted | `#687083` | **slate-500** `#64748b` | Labels, meta, captions |
| Border | `#e9eaf0` | **slate-200** `#e2e8f0` | Card borders, table lines |
| Page background | `#fcfcfe` | **slate-50** `#f8fafc` | App canvas |
| Surface | `#ffffff` | **white** | Cards, header, tables |
| Gain | `#2c795a` | **emerald-700** `#047857` | Up values, success |
| Gain soft | `#edf7f1` | **emerald-50** `#ecfdf5` | Up badge background |
| Loss | `#b3372f` | **red-700** `#b91c1c` | Down values, errors |
| Loss soft | `#fceeed` | **red-50** `#fef2f2` | Down badge background |
| Caution | `#875600` | **amber-700** `#b45309` | Warnings, stale data, pending |
| Caution soft | `#fff5db` | **amber-50** `#fffbeb` | |
| Info / neutral status | — | **sky-600** / **slate-500** | Info alerts, "Running" |

### Dark theme

| Role | Current | Tailwind |
|---|---|---|
| Canvas | `#17151f` | **zinc-950** `#09090b` or **slate-950** |
| Surface | `#211e2d` | **zinc-900** `#18181b` |
| Raised / soft | `#302840` | **zinc-800** + **violet-950** tint for active states |
| Border | `#343044` | **zinc-800** `#27272a` |
| Text | `#eeedf7` | **zinc-100** `#f4f4f5` |
| Text muted | `#b1aec7` | **zinc-400** `#a1a1aa` |
| Primary (text/links) | `#b2a5ff` | **indigo-300** `#a5b4fc` / **violet-300** |
| Primary (filled buttons) | `#6654d9` | **indigo-600** |
| Gain | `#85cfae` | **emerald-300** `#6ee7b7` |
| Loss | `#f29f98` | **red-300** `#fca5a5` |
| Caution | `#f2cc7c` | **amber-300** `#fcd34d` |

Notes:
- The current brand purple sits between Tailwind **indigo** and **violet**. Use **indigo** for the primary scale. indigo-500 is the closest match by eye, but white text on indigo-500 falls just under WCAG AA contrast, so filled buttons use indigo-600. Use **violet-50/100** for soft tints so the app keeps its purple feel. Map Mantine `primaryColor` to a custom 10-step tuple built from Tailwind indigo 50–900.
- The current dark theme has a slight purple tint. If you want to keep it, use zinc neutrals with violet-950 tints. Tailwind has no violet-tinted near-black.
- Check contrast: body text ≥ 4.5:1 and large text/icons ≥ 3:1. Up/down colours must pass on both the soft badge and the surface.

---

## 3. Design direction

### Density (compact)

| Item | Today | Target |
|---|---|---|
| Base font | 15.2px | **14px** (Mantine `sm`). Use 13px in dense tables and meta |
| H1 page title | 36.8px | **20–22px**. Page titles are labels, not heroes |
| Header height | 64px | **48px** |
| Sidebar width | 240px | **220px**, collapsible to **56px** icon rail |
| Control height | 40px | **32px** (Mantine `size="sm"`/`"xs"` for filters) |
| Table row | ~44px | **32–36px**, sticky header, numeric columns right-aligned with tabular numbers |
| Card padding | 16px | **12px** |
| Page padding | up to 32px | **16px** mobile, **24px** desktop |
| Max content width | full | Fluid for tables. Cap reading text (reports, explanations) at ~720px |

### Principles

1. **Lead with the answer.** Each page starts with a compact summary strip (KPIs/status). The detail comes below it.
2. **One page header pattern.** Use the same header everywhere: breadcrumb (if nested) → title + short subtitle on one line → right-aligned page actions. Drop the decorative "eyebrow" lines, such as "The stories behind the signal".
3. **Progressive disclosure.** Methodology text and disclaimers ("How the news bias works", "How to read this valuation") go into an ⓘ `Popover`/`HoverCard` or a collapsed `Accordion`, not inline paragraphs. Each disclaimer appears once per page as a single muted line.
4. **One table pattern.** Every list uses the same toolbar: search → filter chips/selects → "Clear" → result count → density/page size. Filters apply instantly. Remove the separate "Apply"/"Search" buttons, because search is already debounced.
5. **Tabs instead of long scroll.** Pages with many independent sections (Company detail, Ops user detail) use `Tabs`, and the active tab is kept in the URL.
6. **Status is always a badge with an icon.** Use one shared vocabulary of colours (see §5).
7. **Live data looks live.** Use a small pulsing dot plus "Live" or "Delayed · 2m" next to any streaming value. Values that only flash on change (no layout shift).
8. **Empty states teach.** Each one has a one-line reason, one primary action, and for staff a link to the job that fills it.
9. **Keyboard first.** A global `⌘K` / `Ctrl K` search finds companies, IPOs, reports and pages. All tables are keyboard-navigable.

### Open decisions for the designer

- **Corner radius.** Today every corner is forced square (product-wide rule in `brand-tokens.css`). A small radius (4–6px, Mantine `xs`/`sm`) looks more modern. Agree on this with the product owner before you start, because it affects every component.
- **Font.** Today the app uses the system font (Segoe UI/-apple-system). Consider **Inter** with tabular numbers for data.
- **Strict CSP.** Mantine transitions that inject `<style>` tags are blocked. Avoid designs that depend on popover/modal enter animations, or confirm the implementation route with engineering.

---

## 4. Component library (Mantine v8)

| Need | Mantine component |
|---|---|
| App frame | `AppShell` (header 48px, navbar collapsible, `AppShell.Main`) |
| Sidebar items | `NavLink` with icons (react-icons/lucide), `Tooltip` when collapsed |
| Global search | `@mantine/spotlight` (new dependency) |
| Page header | `Breadcrumbs`, `Title order={1}`, `Group` for actions |
| KPI strip | `SimpleGrid` of `Paper` with `Text size="xs" c="dimmed"` label + value + `Badge` |
| Tables | `Table` (sticky header, `striped="even"`/`highlightOnHover`) + TanStack Table (already used), `Pagination`, `Select` page size |
| Filters | `TextInput` with search icon, `Select`/`MultiSelect`, `SegmentedControl` for 2–4 options, `Chip.Group` for quick filters, `Button variant="subtle"` Clear |
| Mobile filters | `Drawer` (bottom) opened by a "Filters (n)" button |
| Sections | `Paper withBorder`, `Card`, `Tabs`, `Accordion` |
| Status | `Badge variant="light"` with `leftSection` icon, `ThemeIcon`, `Indicator` (live dot) |
| Numbers | `NumberFormatter` (INR, %), custom up/down `Text` |
| Help | `HoverCard`/`Popover` + `ActionIcon` ⓘ |
| Feedback | `@mantine/notifications` (replace custom toasts), `Alert`, `Skeleton` for loading, `Loader` inline |
| Confirmations | `@mantine/modals` `openConfirmModal` (replace browser `confirm()` and inline confirm panels) |
| Forms | `TextInput`, `PasswordInput`, `NumberInput`, `Checkbox`, `Switch`, `Textarea`, `FileInput`, `DateInput` (`@mantine/dates`) |
| Charts | Custom SVG candlestick stays. `@mantine/charts` (Sparkline, LineChart, BarChart, DonutChart) for simple charts and Ops metrics |
| Progress | `Progress`, `RingProgress` (accuracy) |
| Code/logs | `Code block`, `ScrollArea`, `CopyButton` |

---

## 5. Shared patterns (design once, reuse everywhere)

### 5.1 App shell

- **Header (48px):** logo `k. kashengine` · global search (`⌘K`) · **market status pill** (e.g. `● NSE open · closes 15:30 IST` / `Closed · opens Mon 09:15`; click opens the trading calendar) · live-connection dot · theme toggle · account avatar menu.
- **Sidebar:** Today, Reports, News, IPOs, Markets, Companies, Delivery. Account and Ops sit at the bottom. Items are hidden when the feature is off. Staff see "Task runs" and "Audit trail" shortcuts, or one "Ops" entry instead. The sidebar collapses to an icon rail, and on mobile it becomes a `Drawer` opened by the burger.
- **Global alerts zone** (top of main, dismissible, max 1–2 visible):
  - Market notice: "Market closed today (holiday reason)" or "Special trading session".
  - Account notice (e.g. trial ending) with a link to Account.
  - App alerts (e.g. live updates disconnected).
- **Account menu (popover):** username, role, subscription state + days left, link to Account, log out.
- **Footer:** small single line with brand, API docs, legal links. Shown on public and app pages.

### 5.2 Trading calendar (modal, from the market status pill)

- Year switcher (‹ 2026 ›) and a month calendar with holiday/special-session markers.
- Below it, a table with Date · Session (Holiday/Special badge) · Reason · hours · circular link.
- Link to the official NSE calendar. Staff also get a "Manage" link.
- States: loading, error + retry, "No dates published for this year".

### 5.3 Data table (used on ~15 pages)

- Toolbar: search, filters, Clear, result count ("1,284 companies").
- Sortable headers with an arrow indicator. Sorting runs on the server for big lists.
- Sticky first column on mobile, plus horizontal scroll.
- Footer: page size (10/25/50/100) + `Pagination`.
- Row hover. The whole row is clickable when it has a detail page.
- Empty state inside the table frame. Loading uses skeleton rows.

### 5.4 Status vocabulary

| Meaning | Colour | Examples |
|---|---|---|
| Positive | emerald | Sent, Success/Done, Right, Included, Active, Live, Bullish, Up |
| Negative | red | Failed, Wrong, Expired, Bearish, Down, Locked |
| Caution | amber | Pending/Waiting, Trial, Delayed, Stale, Mixed, Reconnecting, Single-article evidence |
| Neutral / info | slate or sky | Flat, No session, Not available, Running, Neutral, Withheld |
| Brand | indigo/violet | Symbol chips, primary tags, "Historical simulation" |

### 5.5 Metric value

This is a value with a tone, e.g. `+1.24% ▲`, `7.2 / 10`, `0.43`. Score values get a tiny 5-step strength bar (weak→strong) instead of the "strength legend" paragraph repeated on several pages.

### 5.6 Live price

- Price, then change and change % (coloured, with an arrow), then a freshness tag: `Live`, or `Delayed · 3m` when older than 60s.
- Connection states: Connecting, Live, Reconnecting, Signed out, Unavailable, Not supported.

### 5.7 Loading / error / not-found

- Loading: skeletons shaped like the page, not a centred "Loading…" text.
- Error: inline `Alert` with **Retry**. Sections that fail keep their old data and show a small "Refresh failed · showing saved data" badge.
- 401/403: "You don't have access to this" + link to Account.

---

## 6. Public pages (signed out)

### 6.1 Landing — `/`
**Purpose:** explain the product and get visitors to log in or sign up. Signed-in users see "Open your dashboard".

Today's sections:
1. **Hero:** "Less noise. More perspective." · "A clearer view of Indian markets" · CTA *Explore your dashboard* / *Log in* · *See what's inside* · notes "Built for Indian markets" and "Powered by a local AI model".
2. **Illustrative daily brief** mock-up: market outlook "Positive signal", Nifty 50 mini-chart, scored news with reasons, "News, outlook & IPOs / One daily report", "Daily reports by email or Telegram".
3. **Capabilities** "One engine. The whole picture.": six expandable cards. News with a point of view · A more informed outlook · IPOs, beyond the buzz · Know the companies · Your daily market brief · From the engine to you. Each has 2 bullet tags and a link. There is also an aside about the read-only **REST API** with *Explore API docs*.
4. **Workflow** "A simpler research routine.": Collect the signals → Connect the context → Start with the big picture.
5. **Principles** "Research tools. Not a crystal ball.": explanations with signals, accuracy against a baseline, your judgment decides.
6. **Closing CTA:** "Your next market morning, a little clearer."

**Redesign:** a modern SaaS landing. Sticky top bar with Log in / Sign up. Hero with a real product screenshot. A 3×2 feature grid (no `<details>` toggles; show the text). A 3-step strip, then the principles and a footer. Keep the copy tone.

### 6.2 Log in — `/login/`
Fields: **Username**, **Password**. Shows an "invalid credentials" error. Button **Log in** (shows "Logging in…" while pending). Link: *Need an account? Sign up with an invite code*.
**Redesign:** a centred card (360px) with the logo. Add a password visibility toggle (`PasswordInput`).

### 6.3 Sign up — `/signup/`
Fields: **Username**, **Email**, **Password** (+ confirm), **Invite code** (required unless open registration is on), checkbox **I agree to the Terms and Privacy Notice** (links to Legal). Errors per field, e.g. "The invite code is invalid or has already been used." Link: *Already have an account? Log in*.
**Redesign:** same card as Log in. Inline validation and password-strength hint. Explain the invite code ("Ask the admin for an invite").

### 6.4 Sign-up complete
"Your account is ready". Says a verification email was sent, or that sending failed and the user should request it from Account. Button **Log in to your account**.

### 6.5 Email verification result — `/verify-email/…`
Success, or "link expired/invalid", with a link to Account settings.

### 6.6 Access denied / Locked out
- **No access:** the user lacks the feature or subscription. Link to Account.
- **Locked out:** too many failed logins. Says when to retry.

### 6.7 Legal — `/legal/`
Terms of Use + Privacy Notice (long-form text). Needs a readable typographic layout with a table of contents.

### 6.8 404 — Page not found
"404 · Page not found · The page does not exist or may have moved." Buttons **Go to home**, **Open dashboard**.

---

## 7. App pages (signed in)

### 7.1 Today (dashboard) — `/dashboard/`
**Purpose:** the morning overview. In one screen the user answers "what is the market likely to do today, what's moving, and what should I read?" Sections whose feature is off are hidden.

Today's sections (in order):
1. **Header:** "Today" + date + "Your latest saved outlook, stories, and issues."
2. **Welcome** (only if no features are on): "No feature is on for your account" → Account.
3. **Live indices:** Nifty 50, Sensex and so on, each with LTP, change/change %, day range, last trade time, a session badge and a connection badge.
4. **Saved market movers:** market breadth (advancers/decliners) and top gainer/loser cards. Each links to a company.
5. **Stocks to watch today:** news-driven watchlist (details below).
6. **Outlook for {date}:** "The Nifty 50 is likely to **rise / fall / stay flat**", or "Prediction withheld by the watchdog". Shows a direction arrow, **Signal strength x/10 (label)**, **News score (from n articles)**, **Global markets score**, notes, and a table of the **Strongest cues** (Instrument · Change · Trading date, top 5). Empty state: "No outlook yet". Staff get a link to Jobs.
7. **Prediction statistics:** correct/total days, accuracy, baseline accuracy, warning if too few results → *See the history* (Markets).
8. **Today's news:** positive and negative stories. Each shows headline (external link), "Good/Bad for stocks", source, time → *All news*.
9. **Today's IPOs:** three groups: *Likely to do well*, *Open now*, *Opening soon*. Each has name, dates/status and verdict/score → *All IPOs*.
10. **Market closes:** last saved closing values.
11. **Latest report:** date + link to the report.

**Stocks to watch** card contents: title "Stocks to watch today" · session date · session badge (*Session open at snapshot* / *Pre-open snapshot* / *Session ended* / *No session today*). Per stock:
- Company name (link), symbol, sector, live price.
- **News bias badge:** Bullish (emerald) / Bearish (red) / Mixed (amber) / No clear edge (slate).
- Bias explanation, article and source counts, a "Single-article evidence" warning, and the latest news time.
- Positive/negative story counts and up to 3 headlines (source, time, reason).
- **News balance** −1…+1 (not a probability).

The panel also has a footer about the snapshot and window, and an accordion "Why these stocks? How the news bias works". States: market ended/closed (shows next session), "No news-backed stocks to watch yet".

**Redesign:**
- **Row 1 (KPI strip):** Outlook card (direction + strength bar + accuracy %) · 3–4 live index tiles with sparklines · market breadth bar.
- **Row 2 (2 columns):** *Stocks to watch*, shown as a compact list. Each row has name/symbol, live price, bias badge, article count, and expands to show headlines. Next to it: *Today's news* (top 6, with a sentiment dot).
- **Row 3:** IPOs as tabs (Likely to do well / Open now / Opening soon) · Top movers · Latest report preview (first 3 lines + "Read").
- Move "Prediction statistics" into the Outlook card. Move "Market closes" into the index tiles.
- All methodology goes behind ⓘ.

### 7.2 Reports — `/reports/`
**Purpose:** archive of the daily market reports (the same text sent by Telegram/email).
- Header copy explains Telegram delivery and the score scale.
- Filters: **Search** (date/text), **Outlook** (All/Up/Down/Flat/Not available), Clear.
- Table: **Report date** (link) · **Outlook** (Up/Down/Flat, tone) · **Strength** (x/10).
- Empty state (filter-aware). Staff get "Rebuild report".

**Redesign:** a compact table with an outlook badge and a strength bar. Optional calendar-heatmap toggle (month grid coloured by outlook). Make the whole row clickable.

### 7.3 Report detail — `/reports/{day}/`
**Purpose:** read one day's brief and see whether it was delivered.
- Breadcrumb "All reports" · date · outlook + strength.
- **Report text:** the full body.
- **Delivery:** table of Time (IST) · Channel · Result (Sent/Failed) · Diagnostics, with a status filter. Empty: "This report was not sent."
- **Older / Newer** report links.

**Redesign:** a reading layout (max 720px). Sticky top bar with ‹ Older · date · Newer › and an outlook badge. Delivery becomes a small collapsible panel or side card ("Sent to 3 channels ✓").

### 7.4 News — `/news/`
**Purpose:** search scored articles and see the sentiment, its reason, and which companies each story affects.
- Coverage tabs: **All / Local / International**.
- Filters: Search (debounced), **Score** (sentiment bucket), **Source**, Apply, Clear. Article count.
- Table: **Article & context** (title link, AI explanation, related companies, "Not scored yet") · **Source** · **Region** · **Published** (IST) · **Sentiment** (−1…+1, toned) · **Relevance** (0…1).
- Staff empty-state links: Feeds, Jobs.

**Redesign:** a feed-style list of dense rows. Left: a sentiment pill (▲ +0.62). Middle: headline (one line), the reason (one line, muted), and company chips. Right: source · time-ago. Coverage becomes a `SegmentedControl` in the toolbar. Add a quick filter chip for sentiment (Positive/Neutral/Negative). Relevance shows as a small bar. Rows open the source in a new tab, with an external-link icon.

### 7.5 IPOs — `/ipos/`
**Purpose:** compare current and upcoming IPOs and see the engine's verdict.
- Header notes the verdict inputs and that GMP is unofficial.
- Filters: Search, **Status**, **Verdict**, **Board** (Mainboard/SME), Clear.
- Table: **Issue** (link) · Board · Status · Dates · Price band · **GMP** (toned %) · Subscribed (×) · **Listing gain** (toned %) · **Verdict** · **Score** (−1…+1).

**Redesign:** status tabs at the top (Open · Upcoming · Listed · All) with counts. The table keeps all columns, with the verdict as a coloured badge and the score as a small diverging bar. Pin the Issue column on mobile.

### 7.6 IPO detail — `/ipos/{id}/`
**Purpose:** understand one IPO and why it got its verdict.
- Breadcrumb "All IPOs" · name · category + status · **verdict** + score.
- **The issue:** a facts list (dates, price band, lot size, GMP, listing gain, etc.) + source link.
- **How the verdict was made:** score-scale note. Table **Signal · Value · Signal (1–10)**. Notes, scored time, "not investment advice". Empty: "There is no usable signal yet."
- **Upstox IPO details** (optional): saved time, plus an accordion "Timeline, registrar, subscription and complete saved facts".

**Redesign:** two columns. Left: a key-facts grid (2–3 columns of label/value) and a timeline (Open → Close → Allotment → Listing) as a Mantine `Timeline`. Right (sticky): a verdict card with the score gauge and a signal breakdown (horizontal bars per input). Raw Upstox facts go into a collapsed section.

### 7.7 Markets — `/markets/`
**Purpose:** show the prediction track record and saved index closes.
- Header links: *View company market data* (→ Live), *NSE & BSE instruments*.
- **Track record:** correct/total, accuracy against the baseline, a warning if under ~30 results. Mini stats: *Strong signals* (x of n right), *Last n days*, *Waiting for the result*.
- **Last close:** saved index closes.
- **Predictions** (latest 30): **Day · We said** (Up/Down/Flat/Withheld) **· Strength · It was · Change · Result** (Right/Wrong/No session/Waiting). Filters: Result, Direction.

**Redesign:** use sub-tabs for the 3 Markets pages (Overview · Company quotes · Instruments). KPI strip: accuracy `RingProgress` against the baseline, strong-signal hit rate, last-n, pending. Add a small hit/miss strip chart (one square per day, green/red/grey). Then the predictions table with result badges.

### 7.8 Company quotes (live) — `/markets/live/`
**Purpose:** search the latest saved Upstox price observations per company. The page does not call the provider live.
- Alert if Upstox ingestion is disabled (old data still shown).
- Search: company name/symbol.
- Table: **Company** (link if Companies is on) · Symbol · **Price (INR)** · **Change %** · **Source & time** (freshness tag or "Not fetched") · **Refresh status** (error text or "No recorded error").
- Server pagination. Sorting is not available today.

**Redesign:** this page could merge into Companies as a "Price" column with a freshness tag. If kept, show the error column as an icon + tooltip, and add sorting by change %.

### 7.9 Instruments — `/markets/instruments/`
**Purpose:** a lookup in the imported NSE/BSE instrument master (no prices).
- Filters: Search (symbol/name/ISIN), **Exchange** (All/NSE/BSE), **Segment**, **Instrument type**, Clear. Result count.
- Table: **Symbol** (+ linked company) · Exchange/segment · Type · Underlying/ISIN · Expiry/strike · Lot size.

**Redesign:** a plain dense reference table. Exchange as a `SegmentedControl`. Monospace for ISIN. Hide expiry/strike for equities.

### 7.10 Companies — `/companies/`
**Purpose:** browse and search the company directory.
- Filters: **Search** (name/symbol/sector), **Sector**, **Nifty index** (default NIFTY 50, with constituent counts), Clear. Warning if index lists are not loaded.
- Table: **Company** (link + Screener external link) · **Symbol** (chip) · **Exchange listings** (NSE:XYZ, BSE:123) · **Sector** · **Data from** (date).
- Staff: button **Update company list**, with progress/success/failure messages.

**Redesign:** a toolbar with the index as a prominent `Select`/chips (Nifty 50 · Next 50 · 100 · 500 · All) and sector as a `MultiSelect`. Add price/change/sparkline columns if the data allows. The staff action moves to a page-header "⋯" menu, and its progress shows as a notification.

### 7.11 Company detail — `/companies/{id}/`
**Purpose:** everything about one company: price and chart, the engine's view, news, fundamentals, valuation and IPO history. This is the longest and densest page.

Today's sections:
1. **Hero:** ← Companies · Screener link · **name** · symbol badge · NSE/BSE badges · sector · instrument key · **live price** block.
2. Per-section refresh-failure alerts.
3. **KPI cards:**
   - *Trading session*: previous close (INR), volume, observation type.
   - Or *Company profile* fallback.
   - *Engine outlook*: Bullish/Bearish/Neutral/Withheld, signal score, target date, input checks, momentum score, news score.
   - *News sentiment*: article count with positive/neutral/negative counts.
   - *Data coverage*.
4. **Section nav pills:** Price & trend · Prediction review · Summary · Fundamentals · Valuation · News · IPO scores.
5. **Company summary:** the provider's business description.
6. **Market price & trend:** the **candlestick chart** (details below), quote summary, and the live quote with market depth.
7. **Prediction accuracy & deviations:**
   - Horizon selector (Next session / 5 / 20 sessions).
   - *Chart projection* "Historical simulation".
   - Stats: direction correct %, a progress bar, matched/total, average miss in INR and %, the no-change baseline miss, and a comparison alert (better/no improvement/worse).
   - *Latest comparison*: target date, matched badge, projected vs actual, difference, related news.
   - Accordion with a deviations table.
   - *Saved engine outlook* panel "Direction only": Matched/Missed/Pending/Not verifiable history.
8. **Trade setup watchlist:** three rows (Swing long · Positional long · Intraday/short). Columns: **Style · State & rationale · Condition & risk plan** (entry trigger, stop, risk/share, risk %, illustrative 2R). States include *Watch for confirmation*, *Trend-aligned watch*, *Wait / stale history*, *Need 50 sessions*, and so on. Strong "not a recommendation" disclaimer.
9. **Valuation "Is this company overvalued?":** verdict (*Sector premium / discount / In line / Mixed / Insufficient data*), "n of 3 multiples comparable", and saved time. Table **Multiple · Company · Sector · Comparison** for P/E, P/B, EV/EBITDA. Accordion "How to read this valuation".
10. **Fundamentals:** a dynamic nested facts list from the provider, with units and periods. Note that sector market cap ≠ company market cap.
11. **Company news:** sentiment summary badges and the latest 30 articles. Filters: Source, Sentiment. Fields: title, source, time, sentiment, relevance, reason.
12. **IPO scores:** linked IPO cards (verdict, score, text) and an accordion "All IPO scoring inputs".

**Candlestick chart:** OHLC candles (green up / red down), optional volume bars, SMA 20, SMA 50, and a dashed 20-session history-only projection. A readout shows the date, O/H/L/C, volume and the MAs. Controls: **1M / 3M / 6M / All**, zoom in/out, Earlier/Later, Reset, **Fullscreen**, and toggles for Volume / SMA20 / SMA50 / Projection. Supports mouse drag/hover, keyboard arrows, +/− zoom and Esc.

**Live quote:** LTP, change, open, high, low, previous close, volume, average price, total buy/sell quantity, a buy/sell pressure bar, and a top-5 market depth table (bid qty/price · ask price/qty).

**Redesign:**
- **Sticky company header (compact):** name · symbol · exchange badges · sector · live price + change · freshness. Right side: Screener link and a "⋯" menu.
- **KPI strip (one row of 5):** Prev close · Volume · Engine outlook (direction + score) · News sentiment (mini stacked bar +/0/−) · Valuation verdict.
- **Tabs** (in the URL) replace the long scroll and the anchor pills:
  1. **Overview:** chart (left, ~65%) + live quote/depth (right) + business summary.
  2. **Signals:** engine outlook history + prediction review + trade setups.
  3. **Fundamentals:** valuation table + fundamentals grouped in cards.
  4. **News:** filterable list.
  5. **IPO** (only if linked).
- Chart toolbar on one line: range `SegmentedControl` · overlay `Chip`s · zoom `ActionIcon`s · fullscreen.
- Each disclaimer becomes one muted line + ⓘ.

### 7.12 Delivery — `/delivery/`
**Purpose:** see whether the daily report reached each Telegram/email channel.
- Header: number of configured Telegram chats. Staff get a setup link. Non-staff see "not sent yet".
- **Latest attempts** (newest 50, IST). Filters: Status (Sent/Failed), Channel (Telegram/Email).
- Table: **Time** · **Channel** (chip) · **Report** (date or "Test", link) · **Result** badge · **Diagnostics** (staff only).

**Redesign:** a KPI strip (last delivery time, 7-day success rate, channels configured) and the compact table. Group by report date, e.g. "28 Oct · 3/3 sent ✓", expandable to see each channel.

### 7.13 Account — `/account/`
**Purpose:** manage the subscription status, report delivery preferences, feature access and API tokens. This page is always reachable, even when the user is locked out.

1. **Header:** "Your account", username, email.
2. **Subscription:** state badge (*No subscription / Trial / Active / Expired / Staff*), end date, days remaining, price/period/currency, contact text. Shows "A subscription is not currently required" when that applies.
3. **Report delivery:**
   - Checkbox **Email reports to {email}**, disabled until the email is verified. **Send verification email** button.
   - Telegram status: Connected (@bot) / Not connected. **Link Telegram** generates a link, then "Open Telegram to finish linking". Once connected: checkbox **Send reports through Telegram** + **Disconnect**.
   - **Save report settings** button.
4. **Features:** table **Feature** (+ help text) · **Access** (*Included* / *Not on your account* / *Locked until you subscribe*).
5. **API access:**
   - Explanation + API docs link.
   - New token alert: shown once, "Copy this token now".
   - Token table (latest 20): Name · Token (masked) · Last used · Ends · State · **Revoke** (inline confirm).
   - Create form: **Token name** (max 60) + **Make token**.

**Redesign:** a settings layout with a left sub-nav or `Tabs`: **Profile & plan · Notifications · Features · API tokens**.
- Delivery uses `Switch`es that save instantly, with a notification, so the Save button goes away. Each channel is a row: icon · status · action.
- The new token appears in a `Modal` with `CopyButton`.
- Revoke uses a confirm modal.
- Show an email-verification banner at the top when the email is unverified.

---

## 8. Ops area (staff only)

The Ops area is a separate workspace inside the app. Staff can see it; only superusers can make changes. **Most Ops pages are generic.** The server returns a title, a description, and a list of sections, each with a table, forms, links and/or a chart. So the designer should **design the generic building blocks once** (page header, section card, server table with filters, row-action column, action form, status cell, time-series chart, result alert) and then check them against the page list below.

**Navigation:** a sidebar with 3 groups. When in Ops, the main sidebar is swapped for this one. A sticky tab bar shows the pages of the current group.
- **Activity:** Overview · Jobs · Task runs · Logs · Metrics · Schedule
- **Access:** Users · Invite codes · Subscriptions · Logins · Audit trail
- **Data & configuration:** Feeds · Instruments · Configuration · Settings · Backups (superuser only)

**Generic building blocks today:**
- **Header:** "Operations / {scope}", title, icon, description.
- **Result alerts:** success/warning/info/error.
- **Filters:** search (max 200 characters) + server-defined selects ("All {x}"). Logins adds a time window (24h/7d/30d/All). Logs adds minimum level, logger contains, tail entries (1–1000) and a live-updates checkbox.
- **Cells:** text, IST time, link, or tone (positive ✓ / negative ✗ / warning ⚠ / neutral ⓘ). Missing values show "–".
- **Row actions:** a sticky-right **Actions** column.
- **Forms:** hidden, text, password, number, date, file (.json/.enc), checkbox, select and textarea fields, with help text and errors. Button icons by type: Save, Upload, Download, **Delete (red)**, **Run (play)**. Optional confirmation text. While pending, the button shows "Working…".
- **Charts:** time series (metrics).

### 8.1 Overview — `/ops/`
**System health** (Overall state, checked at, users with sessions) · health-check groups (each check ✓/✗) · **Active runs (latest 8)** · **Recent runs (latest 8)** · **Failed logins (top 6 addresses, 24h)**. Auto-refreshes.
**Redesign:** a status board. One large "All systems OK / n issues" banner, a grid of health checks as compact tiles (Database, Redis, Workers, LLM, Broker, Upstox…), then two columns: active/recent runs and failed logins.

### 8.2 Jobs — `/ops/jobs/`
Lists the jobs an admin may start by hand. Each job has a **label, description, group** and an optional **confirm text**, and is a Celery task or a fixed command. Groups: **Markets, Checks, News, Companies, IPOs, Report, System, Forced runs**. Each job has a **Run** button. A job that is already waiting or running is "busy" and cannot start again for 30 minutes. If the queue is down, the user sees an error. There is also a **Job activity (last 7 days)** table with runs, success rate and active count per job.
**Redesign:** jobs grouped under group headers in a dense table. Columns: Job + description · last run (time + status badge) · 7-day success % · **Run** button (disabled with a "Running…" spinner when busy). Use a confirm modal for jobs with confirm text. "Forced runs" gets a red/amber caution header. A notification appears when the job finishes, with a link to the run.

### 8.3 Task runs — `/ops/runs/`
Header: "Every recorded task or command… Old runs are deleted after N days" + *Manage jobs*.
Filters: Search (job, task ID, user), **Job**, **Result** (Waiting/Running/Done/Failed), **Started by** (Automatic/Manual), Clear.
Table: **Job** (link) · **Started** · **Time** (duration) · **Started by** (user / "Schedule or another task") · **Result** badge.

### 8.4 Run detail — `/ops/runs/{id}/`
Title = job label + status badge. Actions: **Refresh now**, **Stop task** (when active). Notes: "This run updates live while waiting or running", and guidance for runs that stay pending.
Metadata: Queued · Started · Finished · Time · Started by · Worker · Task (code) · Task ID (code) · Arguments.
Panels (when present): **Error** (red) · **Result** · **Output** (terminal `<pre>`).
**Redesign:** metadata as a 2–3 column description grid. Output in a dark monospace `ScrollArea` with Copy and Wrap toggles. A live pulse dot while running.

### 8.5 Logs — `/ops/logs/`
"Application logs" → **Log entries** table (time, level, logger, message). Filters: minimum level, logger contains, tail count, **Live updates**.
**Redesign:** a console-style view. Monospace, level as a coloured tag, sticky filter bar, auto-scroll when live, expand a row for the full message.

### 8.6 Metrics — `/ops/metrics/`
Sections: **Host**, **Redis**, **Sentiment scoring (LLM)**, **Prediction accuracy**, **Workers**, **Jobs (7 days)**, time-series charts (Task runs, News articles fetched, News articles scored, Telegram deliveries, Logins), **Database**. A section says "{X} does not answer" when it is down.
**Redesign:** a dashboard grid of stat tiles and `@mantine/charts` area/bar charts with a shared time range.

### 8.7 Schedule — `/ops/schedule/` (+ add/edit)
**Schedule entries** table: job, timing, state On/Off, row actions (edit, toggle, delete). Action: **Replace my schedule with the default schedule** (confirm). The add/edit page has a form (job, timing) and an **Upcoming runs** preview.
**Redesign:** show the timing in plain English ("Weekdays at 08:30 IST"). Use an On/Off `Switch` in the row. Edit in a `Drawer`, with the next 5 run times shown live as the user types.

### 8.8 Users — `/ops/users/` and user detail
List: username, email, role, active On/Off, subscription state, features. Filters: state, role, active.
User detail: **Account** (fields + Active state + actions), **Feature access** (per feature On/Removed + toggle), **Subscription history (latest 10)**, **Open sessions**, **API tokens (latest 20, masked)**, **Login events**, **Admin actions (latest 15)**, **Ops actions (latest 15)**, **Triggered runs (latest 10)**.
**Redesign:** a user header (avatar, name, role, status badges, key actions). Tabs: Profile & access · Subscription · Security (sessions, tokens, logins) · Activity.

### 8.9 Invite codes — `/ops/invites/`
Form to create an invite (optional email). **Invitations** table: Invitation · State (unused/used/revoked) · Email · actions (revoke). Note: "Copy each new code from the success message and share it privately."
**Redesign:** "New invite" button opens a modal, then a result modal with the code and a `CopyButton`.

### 8.10 Subscriptions — `/ops/subscriptions/`
Users with subscription state, dates and actions (grant trial, extend, end). Plus **All-user subscription counts** (by state).
**Redesign:** KPI strip of counts by state, then the table with row actions in a "⋯" menu.

### 8.11 Logins — `/ops/logins/`
"Logins and lockouts": **Login events** (time, user, address, result), **Failed logins (top 10 addresses, 24h)**, **Current lockouts** (with an unlock action). Time window filter.

### 8.12 Audit trail — `/ops/audit/`
A record of jobs, sessions, account changes and token actions. Names are kept after an account is renamed or deleted. Filters: Search (admin, action, target, detail, address), **Recorded admin**, **Action**, Clear. Table: **Time · Admin · Action · Target** (+ detail, muted) **· Address**.

### 8.13 Feeds — `/ops/feeds/`
"News feeds": table of feeds with name/URL/region, state On/Off, and a **Turn on/off** action. A form to add a feed.

### 8.14 Instruments — `/ops/instruments/`
"Market instruments" used for global cues and indices: name/key, state On/Off, actions. A form to add one.

### 8.15 Configuration & Settings — `/ops/config/`, `/ops/settings/{group}/`
**Setting groups** (links to each group) and **Environment (read only)**. A group page has a **Settings** table/form (key, value, help) and Save.
**Redesign:** a left list of groups and a right form. Show which fields differ from the default, and save per group with a sticky footer bar.

### 8.16 Backups — `/ops/backups/` (superuser)
**Automated encrypted backups:** settings form (schedule, retention, key) → *Save backup settings*. **Manual snapshot:** *Download*. **Replace entire database:** file upload + type `RESTORE` to confirm (destructive).
**Redesign:** the restore section goes in a red "Danger zone" card with an explicit typed confirmation in a modal.

---

## 9. Live / real-time behaviour (applies across pages)

- A WebSocket pushes: live index/company quotes, job completion ("Job completed" / "Job failed" with a link to the run), and session changes.
- Show a "Live updates unavailable / disconnected" alert when the connection drops, and auto-reconnect.
- Ops Overview, Run detail, Logs (live mode) and some Ops pages refresh themselves on an interval.
- The design needs: a connection indicator in the header, a value-change flash, a "last updated" label, and a pause/resume control on Logs.

---

## 10. Responsive behaviour

| Breakpoint | Layout |
|---|---|
| ≥ 1280px | Sidebar expanded. Dashboard 3 columns. Company detail chart + quote side by side |
| 768–1279px | Sidebar as icon rail. 2 columns |
| < 768px | Sidebar becomes a burger `Drawer`. 1 column. Filters in a bottom `Drawer`. Tables scroll horizontally with a pinned first column, or key tables (News, Stocks to watch, Delivery) switch to a card list |

---

## 11. Deliverables requested from the designer

1. Foundations: colour tokens (light/dark, Tailwind steps above), type scale, spacing, radius decision, icon set (Lucide).
2. Mantine theme overrides (component defaults for the compact density).
3. Shared components: app shell, page header, KPI tile, data table + toolbar, status badges, metric value / strength bar, live price, empty/loading/error, confirm modal, notification.
4. High-fidelity screens: Today, Company detail (all tabs), News, IPOs list + detail, Reports list + detail, Markets, Companies, Delivery, Account.
5. Ops: the generic workspace template + Overview, Jobs, Run detail, Logs, User detail, Backups.
6. Public: Landing, Log in, Sign up, 404.
7. Mobile versions of Today, Company detail, News and Account.

---

## 12. V2 mock preview

The redesign is available inside the existing app at `/v2/`. It remains staff-only while the UI is under review and uses the existing Django login/session. Authenticated data pages use the existing typed `/api/app/` endpoints, account actions use the existing persisted account APIs, and Ops actions use the existing staff endpoints. The preview does not require separate V2 tables or migrations.

The preview includes the authenticated pages (Today, Reports and report detail, News, IPOs and detail, Markets with direct Live quotes and Instruments routes, Companies and detail, Delivery, Account, and Design System), the staff-only Ops surfaces (overview, jobs, runs, logs and SMTP queue, metrics, schedule, users and detail, invites, subscriptions, logins, audit, feeds, instruments, configuration, and backups), and public Landing, Log in, Sign up, legal, sign-up completion, email verification, access-unavailable, and not-found states. Public marketing/legal content and the component gallery are static; auth uses the existing Django flows. Only controls backed by existing APIs should perform writes. Do not use the concept screenshots as app assets; the preview uses the concept HTML for layout reference only.

The preview's route and access rules are implemented by `frontend/src/routes/v2.tsx` and `apps/web/urls.py`. Before public release, review authentication, legal content, and permissions for any public-facing pages.
