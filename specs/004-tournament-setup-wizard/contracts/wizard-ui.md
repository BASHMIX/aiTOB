# Contract: Tournament Setup Wizard UI

## Routes and ownership

- `/admin/tournaments/new` creates a draft and redirects to its provider step.
- `/admin/tournaments/setup/:draftId/:step` resumes a protected draft.
- `:step` is `provider`, `tournament`, `discord`, `assistant`, or `review`.
- The route never accepts workspace identity. A missing/inaccessible draft shows
  the same not-found state.
- The former direct-import form routes new work into the wizard. Existing
  tournament settings continue to edit materialized tournaments.

## Shell

Desktop uses a stepper, one primary content column, and a compact current-summary
column. Mobile uses one column and a sticky action bar. Each step is a real form
with one `<h1>`. Back never destroys later answers. Next flushes autosave and
validates the current step.

The stepper is `<nav aria-label="Tournament setup"><ol>…</ol></nav>` and marks
the current item with `aria-current="step"`. It exposes Complete, Current,
Needs attention, and Optional skipped using text/icon plus color.

## Save behavior

The frontend store holds a working copy, dirty section names, field errors,
revision, and `idle | saving | saved | retrying | failed`. It never stores API
keys, OAuth codes, bot tokens, or raw provider errors. API key input is local
component state, submitted directly, then cleared.

- Debounce ordinary changes by about 800 ms.
- Flush on Next, meaningful blur, logo upload, and before authorization redirect.
- Send one section and the current revision.
- Ignore stale responses older than the latest local request sequence.
- On network failure, keep editing available and retry with bounded backoff.
- On `409`, stop autosave, show a conflict panel, and let the organizer reload the
  server copy or explicitly reapply their visible local changes.
- Announce save status in a polite live region; do not repeatedly announce idle.

## Step 1: Provider and scope

The opening choice is two clear provider cards: Start.gg and Challonge. Existing
connections appear first. “Connect” launches OAuth; “Use another connection” is
secondary. Returning from OAuth restores the same draft/step.

Start.gg labels the field “Event link or Event slug” and explains that Event is
the most precise input. A separate “Tournament link” path may list Events. A
direct Event resolution highlights one selected Event for confirmation. A
multi-Event tournament renders a radio/list choice and blocks Next until the
organizer selects one. No first item is preselected.

The preview includes provider account, tournament, Event/bracket, game, date,
state, observation time, and missing facts. Retry keeps the locator and later-step
answers.

## Step 2: Tournament and operating profile

Render provider facts in a read-only group with source/freshness badges. Render
local presentation fields separately: display name, short name, timezone where
provider data is absent/insufficient, logo, and accent color. Preview the shared
identity used by Hub, Editor, and overlay.

Offer two presets with plain-language summaries:

- **Manual**: organizer calls matches and controls operations.
- **Assisted**: bot can call eligible matches within concurrency/freshness rules,
  send reminders, and escalate attendance/results to a human.

Advanced settings contain attendance source/duration, reminders, escalation,
human result approval, automatic calls, concurrent matches, automatic-call stop
threshold measured in unfinished matches, and stream handling. Do not show automatic DQ.
Explain the stop threshold as a count of unfinished matches.

For Start.gg, show Start-in-wave as Enabled, Disabled, Unsupported, or Unknown.
This Epic does not show a remote toggle. For unsupported/unknown, provide a link
to provider settings and “Recheck” without implying aiTOB changed it. The
organizer may explicitly select “I enabled Start in wave in Start.gg”; this is
shown as Organizer confirmed with its time, not as provider verification, and
can be revoked.

When provider-verified or organizer-confirmed enabled, the operating summary says
that aiTOB will wait for bracket start, synchronize every Start.gg transition to
`CALLED`, and send the same Discord player call used for a Dashboard transition.
Runtime status distinguishes Waiting for bracket start, Monitoring provider
matches, and Monitoring paused. Source labels may identify Start.gg or Dashboard,
while delivery uses one deduplication key per match call occurrence.

## Step 3: Discord

The first control is Enable Discord for this tournament. When off, show the
manual-operation consequence and allow Next. When on:

1. Select/reuse or connect a Discord server installation.
2. Select match destination, escalation destination, and optional moderator role
   from named lists.
3. Select channel/thread/DM-with-fallback behavior.
4. Review effective permissions and identity-link coverage.
5. Customize language, tone, and supported templates.
6. Preview messages with synthetic values.

Permission rows name the missing capability and affected destination and include
a recheck action. Guild identity customization is clearly labeled server-wide;
tournament logo/color/name customize message content.

### Player registration subsection

Place a collapsed **Player registration** card after Discord readiness. Its
header shows Off, Scheduled, Open, Closed, or Needs attention and the current
window. Enabling it reveals fields in this order:

1. Registration channel or thread from the selected guild.
2. Opening date/time, closing date/time, and IANA timezone, with a readable local
   summary and server-validated `opening < closing` rule.
3. “Require registration on the tournament provider” toggle, on by default for
   imported tournaments. Supporting text explains that turning it off permits a
   Discord-only record, while provider match automation waits for an exact entrant
   link.
4. Verification method: exact Discord name equals provider Gamertag, bot changes
   the member's server nickname to Gamertag, or either. Show an optional separate
   Start.gg bio-code switch only for Start.gg. For Challonge, keep the configured
   Gamertag/nickname method and omit the bio switch.
5. Player image choice: Disabled, Optional (recommended), or Required; explain
   Keep existing, Replace, and Skip behavior.
6. Optional verified-player role, registration messages, and reminder schedule.

Show a compact preview and sample status rows with separate `Prefix`, `Gamertag`,
and Discord name columns. Start.gg copy explains that bio code is optional and
the player must appear in the exact Event when provider registration is required.
Challonge copy explains that it uses the selected exact Gamertag/nickname rule.
If two normalized Gamertags collide, the UI shows Needs review and never silently
chooses one.

The organizer status drawer groups counts as Waiting for provider, Waiting for
Discord link, Waiting for identity, Waiting for image, Waiting for review, Ready, Rejected, and Needs
review. Filters preserve keyboard focus and expose one clear corrective action
per row: Add Discord ID, Edit Discord ID, Unlink, Recheck, Approve exact link,
Request image, Reject, or View evidence summary. Each provider entrant row shows
Prefix, Gamertag, Discord name, masked/full authorized Discord ID, link state, and
one contextual link action. Editing opens a compact labeled field beside or below
the selected row rather than making every cell permanently editable.

Saving a Discord ID shows Resolving, then Linked, Not in server, Invalid, or
Conflict. The dialog explains that the ID must belong to a non-bot member in the
selected server and that one Discord account can represent only one entrant in
this tournament. Evidence summary shows IDs, source, freshness, and safe reason codes,
never bio content, verification codes, image bytes, or provider raw payloads.

Before opening, the bot action is disabled and states the opening time. After
closing, it states the closing time and refuses new starts or confirmations.
Opening/closing announcements, role grants, duplicate clicks, and refreshes show
one resulting effect. A player removed from the provider roster becomes Needs
review without losing their Workspace identity or image.

## Step 4: Organizer assistant

Keep every current assistant setting and meaning: provider, model,
disabled/read-only/propose-only mode, hourly request/token guardrails, context and
response limits, timeout, and enforced safety policy.

Add Gemini and OpenAI connection cards. Each card shows configured, enabled,
health category, and last test time only. Owner-authorized users can add/replace a
write-only API key, explicitly test, disable/enable, or remove it. Other users see
safe status and a message that an Owner manages credentials.

Copy states that the chosen provider bills the workspace owner directly and
aiTOB does not sell AI tokens. It warns that an explicit test can consume a small
amount of provider quota. Provider/model switching does not erase the other
saved connection or reset assistant controls.

Translation, player chat, and result understanding appear as unavailable future
capabilities, not functional toggles. Skipping AI leaves templates and manual
controls available.

## Step 5: Review and outcomes

Show one card per prior step with `Ready`, `Optional skipped`, `Warning`, or
`Blocked`, a short consequence, and an Edit link back to the exact step/field.
Focus the validation summary after a failed final action.

When registration is enabled, the Discord card summarizes its destination,
window/timezone, provider requirement, image policy, and readiness. Invalid dates,
missing destination permissions, or an unavailable exact provider scope block
activation of registration and link directly to the subsection; they do not erase
the rest of the tournament draft.

Present distinct actions and results:

- **Save draft**: preserve work without creating a tournament.
- **Save tournament**: materialize a configured local tournament.
- **Activate aiTOB management**: begin local management and queue initial sync.
- **Start provider bracket**: show only when a separately verified capability and
  fresh preflight support it; otherwise link to the provider and offer Recheck.

Required provider scope, identity, and operating failures block saving the
tournament. Optional Discord/AI warnings require no coercive confirmation.
Actions are idempotent and disable only while their current request is pending.

## Validation and accessibility

- Client validation improves immediacy; server validation is authoritative.
- Field errors use `aria-invalid`/`aria-describedby`; the error summary links and
  moves focus to the field.
- Focus moves to the step heading on navigation and to the first invalid field
  after a rejected Next.
- All disclosures, provider choices, upload/remove actions, template editing, and
  dialogs are keyboard usable. Touch targets are at least 44×44 CSS pixels.
- Status never relies on color alone. Loading skeletons retain labels.
- The layout has no horizontal page scroll at supported mobile widths.
- Logical CSS properties and the document `dir` support Arabic RTL and English
  LTR without reversing numeric/provider identifiers.
- Do not use browser `alert()`/`confirm()`; use accessible in-page/dialog states.

## Frontend acceptance matrix

Vitest/Testing Library covers direct Event selection, multi-Event required
choice, step back/forward preservation, autosave debounce/retry/conflict, reload
and OAuth restoration, secret-field clearing, optional skip paths, permission
failure navigation, registration window validation, provider-required/optional
copy, Gamertag matching/nickname changes, optional Start.gg bio visibility,
Prefix/Gamertag labels, manual Discord ID add/edit/unlink and validation states,
image policy, enrollment filters/actions, all final action labels,
keyboard-only completion, RTL, and mobile layout. Network adapters are mocked;
tests contain no real secrets or paid provider calls.
