# Research: Tournament Results Media

## Decision 1: Final results are event-scoped and provider-authoritative

**Decision**: Capture standings for one selected event. Start.gg is Final only when the selected event reports completed and its paginated event standings validate. Challonge is Final only when the tournament reports `complete` and final-stage participants have `final_rank`; `awaiting_review` remains Provisional.

**Rationale**: A Start.gg tournament may contain several events. Start.gg documents event standings as paginated `placement` plus `entrant`, and defines a standing as an entrant's current or final placement within an event. Challonge documents `awaiting_review` as reviewable and `complete` as the ended state. This preserves the project's rule that providers own bracket progression and avoids inventing placement from local matches.

**Alternatives considered**:

- Derive placement from the local bracket: rejected because local matches can be partial or stale and the provider is authoritative.
- Treat no active matches as complete: rejected because phases can be inactive, paused, or calendar-completed without a publishable final result.
- Treat Challonge `awaiting_review` as Final: rejected because results may still be edited before finalization.

**References**:

- https://developer.start.gg/docs/examples/queries/event-standings/
- https://developer.start.gg/docs/glossary/
- https://challonge.apidog.io/tournament-states-1726857m0
- https://challonge.apidog.io/running-a-two-stage-tournament-1726921m0
- https://challonge.apidog.io/list-participants-23619749e0

## Decision 2: Every refresh creates or reuses an immutable results version

**Decision**: Store an immutable observation containing provider evidence, normalized standing rows, and resolved presentation. Deduplicate identical observations by a provider/presentation payload hash; never update a prior publication version in place.

**Rationale**: Social exports and live overlays must not change when a provider or Player Archive record changes later. A frozen version also gives export/live actions a stable audit target and allows an operator to refresh safely without altering an on-air scene.

**Alternatives considered**:

- Resolve provider and profile data at every render: rejected because it can change mid-show and makes prior exports non-reproducible.
- Copy only final placement and resolve presentation live: rejected because avatar, prefix, country, and character edits would silently change published media.
- Store the complete provider response only: rejected because cutoff queries and validation need normalized standing rows while raw evidence remains useful only as bounded metadata.

## Decision 3: One shared Result Card serves two authoring paths

**Decision**: Keep both Add Result Card and Add Results Group. Add Result Card is the freeform motion-design path. Add Results Group is the template-based social-image and established group-animation path. Both reference the same Result Card definition and renderer.

**Rationale**: The workflows solve different jobs. A designer needs unconstrained cards for gallery-like motion, while an organizer needs ready templates for rapid export. Sharing the card definition prevents duplicated styling, bindings, and bugs.

**Alternatives considered**:

- Remove Results Group: rejected because it discards useful static templates and existing animation behavior.
- Make Results Group the only entry point: rejected because it forces layout/template concepts on simple freeform animation.
- Maintain separate freeform and template cards: rejected because their fields and appearance would drift.

## Decision 4: Persist linked cards but keep generated cards ephemeral

**Decision**: Use three instance forms around one definition: persisted freeform/linked instances, ephemeral Results Group template instances, and ephemeral Auto Sequence runtime instances. Only instances explicitly inserted on the canvas appear in Layers, history, clipboard, or saved JSON.

**Rationale**: Static/manual composition needs real per-card transforms and animation overrides. Template preview and Auto Sequence need cheap repeated render values without polluting authoring state. A definition reference keeps both consistent.

**Alternatives considered**:

- Persist every preview/playback card: rejected because it recreates layer clutter and ambiguous edits.
- Never persist any repeated card: rejected because the user could not freely arrange or animate Top 8 cards individually.
- Deep-copy each card design: rejected because edits would diverge and documents would bloat.

## Decision 5: Card design mode is nested; scene mode treats the card atomically

**Decision**: `Edit Card Design` opens a focused child canvas and child Layers branch. On exit the Result Card is one movable/resizable/rotatable scene object. The same editor is opened from a freeform card or a Results Group card reference.

**Rationale**: This matches component/symbol workflows in design tools and separates “design the card” from “place the card.” It prevents the current confusion between a generated grid, master template, and scene layers.

**Alternatives considered**:

- Always expose internal children in the main Layers list: rejected because placement edits can accidentally modify card internals.
- Use a fixed fields form without canvas children: rejected because it blocks custom size, position, composition, and animation.

## Decision 6: Reuse the existing Animation panel with an overlapping group stagger

**Decision**: A freeform card uses the editor's existing `animation` model and panel. Auto Sequence starts instance `i` at `base + i × delayBetweenStartsMs`; it does not wait for the previous card. Internal-child, atomic-card, and group-schedule scopes remain distinct. Old `outerAnimation` payloads are compatibility input only.

**Rationale**: One animation model keeps the editor predictable and prevents the card from behaving differently from ordinary canvas elements. Start-time stagger still supports gallery-like overlap and multiple simultaneous cards.

**Alternatives considered**:

- One cue at a time: rejected because it cannot show overlapping cards.
- Delay after completion: rejected because the requested delay controls the next start, not the gap after exit.
- Full arbitrary keyframes now: rejected because it substantially expands editor complexity before the focused lifecycle is proven.

## Decision 7: Placement, layout slot, stacking, and playback order are independent

**Decision**: Provider placement identifies content; a Results Group slot optionally identifies template geometry/variant; a freeform transform identifies materialized geometry; playback order identifies start order; z-index controls stacking only.

**Rationale**: The same standings may be arranged by a template, placed manually, or replayed from one stage card. Keeping these axes independent prevents moving a layer from changing placement or playback timing.

**Alternatives considered**:

- Continue using z-index as sequence order: rejected because layer reordering becomes an unsafe timing edit.
- Encode geometry or timing into placement: rejected because templates and playback orders vary without changing provider truth.

## Decision 8: Deterministic local mock datasets drive design preview

**Decision**: Ship frontend-only mock datasets for normal names, long/RTL names, missing media, and ties. Use bundled/local placeholder assets only. Preview range/page drives generated instances without database writes.

**Rationale**: Designers need to complete and test animation before a tournament ends. Deterministic boundary datasets make visual regressions repeatable, avoid external asset dependencies, and ensure mock players never enter Player Archive or tournament records.

**Alternatives considered**:

- Require a real tournament: rejected because it blocks design work and makes tests unreliable.
- Generate random data: rejected because screenshots and sequence tests would be nondeterministic.
- Use third-party placeholder URLs: rejected because they are unapproved external dependencies and can fail or track requests.

## Decision 9: Use the shared DOM renderer and client-side PNG export in v1

**Decision**: Render an unscaled final scene at the chosen output dimensions—either a Results Group Board composition or an explicitly materialized freeform composition—wait for asset/font preflight, and convert the shared DOM node to PNG with `html-to-image`. Save an auditable media-output receipt and config hash before downloading; do not persist PNG bytes in v1.

**Rationale**: The editor and OBS already render in the browser. Reusing that renderer gives the closest preview/export parity without adding a headless-browser runtime, browser binaries, render queue, or another persistent volume. `html-to-image` supports DOM-to-PNG conversion, explicit canvas dimensions, pixel ratio, placeholders, and font embedding.

**Alternatives considered**:

- Python/Pillow poster renderer: rejected because it duplicates layout and typography behavior and cannot reuse editor animations/components.
- Server-side Playwright in v1: technically strong and retains a future path, but rejected initially because it adds Chromium packaging, bounded worker management, an authenticated internal render page, and operational capacity. Playwright can capture element screenshots and PNG buffers if server-rendered exports become necessary later.
- Persist generated PNG files locally: rejected because production currently persists avatars only and PostgreSQL is the runtime state source; exported bytes are a client download in v1.

**References**:

- https://github.com/bubkoo/html-to-image
- https://playwright.dev/python/docs/api/class-page#page-screenshot

## Decision 10: Results use a dedicated overlay projection and persisted session

**Decision**: Extend the station response with an explicit `projection_kind`. A Results session points to a frozen output/result version and persists cue index, state, and revision. The OBS viewer renders Results without an active match and restores a safe state after reconnect/restart.

**Rationale**: Current OBS data is merged into match-specific element IDs and clears standard overlays when no match is active. Reusing that path would blank the post-tournament output. A separate projection preserves the strict OBS boundary and avoids changing match lifecycle semantics.

**Alternatives considered**:

- Fabricate a final match as the overlay data source: rejected because it conflates bracket, Hub, and broadcast state.
- Store cue index only in the browser: rejected because refresh/reconnect loses operator state and multiple controllers can double-advance.
- Add a separate OBS application: rejected because the existing station tokens, browser source, and renderer can be extended safely.

## Decision 11: Use explicit permissions for results operations

**Decision**: Add `results.manage` for Owner/Tournament Organizer and `results.broadcast` for Owner/Stream Operator. Keep `overlay.manage` for general scene design. View-only readiness uses `workspace.read`.

**Rationale**: Refreshing/finalizing a media snapshot and controlling an on-air station are different responsibilities. Explicit permissions make the Roles & Permissions screen accurate and keep server-side enforcement auditable.

**Alternatives considered**:

- Reuse only `tournament.manage`: rejected because it would grant broadcast control to organizers and exclude stream operators.
- Reuse only `overlay.manage`: rejected because tournament organizers need results refresh/export without general station design authority.

## Decision 12: Character is presentation, not competition evidence

**Decision**: Resolve a featured character by established presentation precedence and allow an event-specific organizer override with an explicit promote-to-profile action. Label it featured/selected; never claim match usage without verified game data.

**Rationale**: Character catalog data identifies available characters, not reliably what an entrant used throughout the event. This gives organizers practical control without falsifying provider evidence.

**Alternatives considered**:

- Infer character from the final match: rejected because game data may be absent or incomplete and may not represent the player's event identity.
- Always modify Player Archive: rejected because a one-event correction may not be a durable player preference.
