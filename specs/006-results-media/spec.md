# Feature Specification: Tournament Results Media

**Feature Branch**: `006-results-media`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Create provider-authoritative final standings media around one shared editable Result Card. Add Result Card supports free placement, linked cards, and overlapping Auto Sequence playback; Add Results Group uses the same card inside reusable social-image templates and the previous group-animation workflow."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish a Final Results Graphic (Priority: P1)

As a tournament organizer, I select a completed event, confirm that its final standings came from the tournament provider, choose Top 8, Top 16, or all standings, customize a tournament-branded layout, and export a publication-ready image containing placements and player presentation data.

**Why this priority**: A trustworthy final results graphic is the primary business outcome and establishes the final-results data required by every later broadcast use.

**Independent Test**: Complete a disposable event at each supported provider, open its results, generate a Top 8 graphic from a starter template, and verify every displayed placement and entrant against the provider before exporting the image.

**Acceptance Scenarios**:

1. **Given** a provider-confirmed completed event with final standings, **When** an organizer opens the results studio, **Then** the event is marked Final and its ordered standings are available for Top 8, Top 16, or all-results output.
2. **Given** an event that is active, awaiting review, stale, or missing final placements, **When** an organizer previews its standings, **Then** the output is clearly marked Provisional and cannot be published as Final.
3. **Given** a final event with tied placements, **When** Top 8 is selected, **Then** every entrant whose provider placement is 8 or better is included even when that produces more than eight cards.
4. **Given** a selected output template, **When** the organizer changes branding, field visibility, player-image crop, title, date, or sponsor content, **Then** the preview and exported image reflect those choices without changing provider-owned placements.
5. **Given** missing optional player media, **When** the organizer exports, **Then** the system shows a preflight warning and uses the configured fallback rather than silently omitting the entrant.

---

### User Story 2 - Design One Shared Result Card (Priority: P2)

As a broadcast designer, I add a Result Card, open its design as a focused nested canvas, freely compose its text, image, and shape children, then use that same design as an atomic freeform card or inside a Results Group template.

**Why this priority**: One shared card definition prevents visual drift while supporting both unconstrained motion design and repeatable social-image templates.

**Independent Test**: Add a Result Card, enter Edit Card Design, add and resize player image, prefix, flag, character art, placement, and name, exit design mode, and verify the card becomes one movable object. Add a Results Group and verify its generated cards use the same definition.

**Acceptance Scenarios**:

1. **Given** a blank canvas, **When** a designer chooses Add Result Card, **Then** one Result Card is inserted under an automatically created Results Cards scheduling parent and is selected.
2. **Given** a selected Result Card, **When** Edit Card Design is opened, **Then** its internal bound and literal children are individually selectable, movable, resizable, reorderable, styleable, and animatable.
3. **Given** design mode is closed, **When** the designer manipulates the Result Card, **Then** it behaves as one atomic canvas object that can move, resize, rotate, stack, or sit outside the canvas.
4. **Given** a Results Group template and a freeform Result Card that reference the same card definition, **When** a font, color, image crop, flag position, or child element changes, **Then** every consumer reflects that change.
5. **Given** Long Names, Missing Media, RTL, or Tied Placements mock data, **When** the designer previews either path, **Then** boundary content is shown using local deterministic placeholders without creating or changing real player records.
6. **Given** the Add panel, **When** the designer compares Add Result Card and Add Results Group, **Then** their descriptions clearly distinguish freeform card authoring from template-based image/legacy group animation.

---

### User Story 3 - Animate Freeform Cards and Take Results Live (Priority: P3)

As a stream operator, I animate one freeform Result Card with the editor's existing Animation panel and replay it for Top 8, Top 16, or All with an adjustable delay between starts, or use the existing Results Group animation workflow, then bind the output to a frozen results version and take it live.

**Why this priority**: This turns the reusable design into a safe post-event broadcast package without coupling it to the lifecycle of a live match.

**Independent Test**: Apply the same Animation controls used by a text/image/shape to one mock Result Card, set a 500 ms group stagger, verify overlapping Top 8 instances start at 0/500/1000 ms, and confirm preview completion restores the authored card before taking the result live.

**Acceptance Scenarios**:

1. **Given** one selected Result Card, **When** its Animation settings are edited or previewed, **Then** the exact same Animation panel and behavior used by text, images, and shapes applies, with no separate Card Motion panel or duplicated motion state.
2. **Given** Auto Sequence with a lifecycle longer than Delay Between Starts, **When** playback runs, **Then** multiple runtime cards overlap and each starts exactly at `index × delay` without entering Layers or saved state.
3. **Given** Insert Top 8 Cards, **When** the designer moves or animates individual cards, **Then** each linked instance retains its own transform/override while sharing the same internal card design.
4. **Given** a Results Group, **When** its existing group animation mode runs, **Then** it uses the shared Result Card while preserving its template slots and established sequence behavior.
5. **Given** a completed tournament with no active match, **When** either results output is taken live, **Then** it remains operable until the operator advances, holds, restarts, or clears it.
6. **Given** unloaded required assets or an invalid final-results binding, **When** Take Live is requested, **Then** the action is blocked with an actionable readiness message.

---

### User Story 4 - Correct Player Presentation Safely (Priority: P4)

As a tournament organizer, I correct a participant's display presentation, including the featured character, for the current event and choose whether that correction remains event-specific or updates the reusable player profile before producing a new media version.

**Why this priority**: Providers do not reliably supply the character used by a player, while accurate presentation is important for both social and broadcast output.

**Independent Test**: Change one entrant's featured character as an event override, verify only that event's preview changes, then explicitly promote the correction to the player profile and verify future previews inherit it.

**Acceptance Scenarios**:

1. **Given** a linked player profile, **When** an organizer sets an event-specific character override, **Then** that event's media uses the override without silently changing the reusable profile.
2. **Given** a reviewed event override, **When** the organizer explicitly chooses to update the player profile, **Then** the reusable profile is updated and the action is distinguishable from an event-only edit.
3. **Given** a previously frozen media version, **When** player presentation data changes, **Then** the published version remains unchanged until the organizer creates or refreshes a new version.

### Edge Cases

- The provider reports no standings, duplicate entrant identifiers, null placements, non-monotonic placements, or a partial page of results.
- Start.gg standings exist while the selected event is not provider-confirmed complete.
- Challonge is awaiting review or some final-stage participants do not have a final rank.
- A tournament contains multiple events, phases, or games and the organizer must select the exact event.
- Tied placements cause Top 8 or Top 16 to contain more cards than the nominal cutoff.
- Top 16 or all-results content cannot fit one canvas and must be paged rather than shrunk below legibility limits.
- A player has no linked profile, avatar, flag, character, prefix, or usable image URL.
- Player names contain long text, right-to-left text, emoji, or unsupported glyphs.
- Images fail to load, have unexpected aspect ratios, or violate the configured crop/safe area.
- A final-results version becomes stale because the provider changes results after review.
- An operator opens a results overlay with no active match or restarts the broadcast service mid-sequence.
- Auto Sequence delay is zero, shorter than the card lifecycle, or longer than it, producing simultaneous starts, overlap, or intentional gaps.
- A tied placement creates repeated labels while every entrant still needs a stable editable linked-instance identity.
- A card enters or exits outside the canvas and must not be clamped by template layout logic.
- A shared Result Card is edited while used by both a Results Group and freeform linked instances.
- An existing saved Results Group is opened after introducing the shared Result Card model.
- Two Workspaces use results overlays simultaneously and must not see each other's events, assets, commands, or public links.

## Requirements *(mandatory)*

### Functional Requirements

#### Final standings and versioning

- **FR-001**: The system MUST scope final standings to one selected event and Workspace.
- **FR-002**: The system MUST classify a results fetch as Provisional, Final, Stale, or Failed and explain the reason for any non-Final state.
- **FR-003**: Final status MUST require provider-confirmed event completion and usable provider-owned placements; absence of active matches alone MUST NOT prove completion.
- **FR-004**: Start.gg final results MUST come from the selected event's provider standings after the provider marks that event complete.
- **FR-005**: Challonge final results MUST require a completed tournament and provider-assigned final ranks; awaiting-review results MUST remain Provisional.
- **FR-006**: The system MUST NOT infer, repair, or reorder final placements from local match history.
- **FR-007**: The organizer MUST be able to refresh provider results deliberately and see when the last successful verification occurred.
- **FR-008**: A publishable results version MUST freeze provider standings, resolved player presentation, selected event metadata, verification state, and creation time.
- **FR-009**: Previously published versions MUST remain reproducible after later provider or player-profile changes.
- **FR-010**: Top N selection MUST include all entrants whose placement is less than or equal to N, including ties.
- **FR-011**: All-results output MUST support pagination without changing provider placement order.

#### Player presentation

- **FR-012**: Each result card MUST resolve display name, prefix, country/flag, avatar, featured character, and character artwork through the platform's established presentation precedence.
- **FR-013**: The system MUST label the character as a featured or organizer-selected character and MUST NOT claim it is the character actually used in a match unless a verified source exists.
- **FR-014**: Authorized organizers MUST be able to set event-specific presentation overrides without altering provider-owned placements.
- **FR-015**: Promoting an event override to the reusable player profile MUST require a separate explicit action.
- **FR-016**: Missing optional presentation fields MUST produce visible preflight warnings and deterministic fallbacks.

#### Shared Result Card and authoring paths

- **FR-017**: The Add panel MUST expose both Add Result Card for freeform design/animation and Add Results Group for template-based image and established group-animation output.
- **FR-018**: Both paths MUST consume the same Result Card definition and renderer; they MUST NOT maintain competing Master Card implementations.
- **FR-019**: A Result Card definition MUST allow bound or literal text, image, shape, and nested group children to be added, removed, reordered, moved, resized, styled, hidden, locked, and animated in focused Edit Card Design mode.
- **FR-020**: Outside Edit Card Design, a freeform Result Card MUST behave as one atomic canvas element that can move, resize, rotate, stack, and remain outside canvas bounds.
- **FR-021**: Add Result Card MUST create or use a Results Cards scheduling parent without requiring the user to add a Results Group template.
- **FR-022**: A Results Cards scheduling parent MUST control member order/timing only and MUST NOT impose layout slots or mandatory visual variants.
- **FR-023**: Add Results Group MUST retain template-based layouts, optional Champion/Podium/Standard variants, static export, and the established group animation workflow while using the shared Result Card.
- **FR-024**: Results Group template-generated preview/runtime cards MUST NOT appear as independent editable layers, history entries, clipboard nodes, or saved nodes.
- **FR-025**: Results Group Board/final composition MUST support static export, and its established sequence mode MUST remain available for animated preview/live output.
- **FR-026**: Mock preview datasets MUST include normal data, long names, missing media, RTL, and tied placements; they MUST use local deterministic placeholders and MUST never create or modify real player records.
- **FR-027**: Both paths MUST support Top 8, Top 16, and all-results paging/batching.
- **FR-028**: Results Group templates MUST include Champion Focus, Podium plus remaining entrants, Equal Grid, Ranked List, and a paged layout.
- **FR-029**: An explicit conversion/materialization action MUST be able to turn a Results Group template arrangement into linked freeform card instances without copying the shared card definition.

#### Animation and broadcast operation

- **FR-030**: A freeform Result Card MUST use the same Animation panel, settings, preview action, and runtime semantics as text, image, and shape elements; no separate Card Motion panel or second authored motion model is allowed.
- **FR-031**: Internal child animation, atomic card animation, and parent schedule MUST remain distinct scopes; legacy outer-animation data may be read for compatibility but MUST NOT be authored for new cards.
- **FR-032**: Auto Sequence MUST support Top 8, Top 16, or All; ascending, descending, or custom order; Delay Between Starts; end behavior; and optional looping.
- **FR-033**: Delay Between Starts MUST schedule instance `i` at `base + i × delay`; it MUST permit overlapping animations and MUST NOT implicitly wait for the previous lifecycle to complete.
- **FR-034**: Auto Sequence runtime instances MUST remain ephemeral and MUST NOT enter Layers, saved JSON, clipboard, or undo/redo history.
- **FR-035**: Designers MUST be able to materialize Top 8, Top 16, or a bounded All page as linked card instances sharing one definition but retaining independent transform, stacking, and optional animation override.
- **FR-036**: Optional Gallery/Grid helpers MAY arrange materialized cards once but MUST NOT constrain later movement or regenerate positions implicitly.
- **FR-037**: Playback order MUST remain independent of layer stacking and MUST NOT alter provider placement or result order.
- **FR-038**: Operators MUST be able to preview, play, pause/hold, restart, clear, advance one cue, and return one cue.
- **FR-039**: The established Results Group sequence controls MUST continue to work with the shared Result Card.

#### Static media and controls

- **FR-040**: The shared Result Card renderer MUST be used by freeform scenes, Results Group templates, live overlays, and static image export.
- **FR-041**: Static export MUST support landscape 1920×1080, square 1080×1080, and portrait 1080×1350 output profiles.
- **FR-042**: The organizer MUST be able to customize background, colors, typography, tournament logo, title, subtitle, date, sponsor assets, field visibility, and player-image crop.
- **FR-043**: Initial static export MUST support PNG and produce a preview matching the exported composition.
- **FR-044**: Provider-owned placements and entrant identity MUST be read-only in the results designer.
- **FR-045**: Creating, refreshing, exporting, taking live, and clearing results media MUST be auditable actions attributed to an authorized account.
- **FR-046**: Results design and operation controls MUST respect existing role permissions; unauthorized controls MUST be rejected server-side and hidden from the interface.
- **FR-047**: A results overlay MUST use the existing overlay delivery model while declaring Tournament Results as its data source rather than Current Match.
- **FR-048**: A results overlay MUST remain operable and visible when no match is active.
- **FR-049**: The live overlay MUST bind to a specific frozen results version so a refresh cannot change an on-air sequence unexpectedly.
- **FR-050**: Required assets and bindings MUST pass readiness checks before Take Live.
- **FR-051**: Public results-overlay access and operator commands MUST remain scoped to the owning Workspace, station, and revocable authorization.

### Key Entities

- **Event Results Source**: The selected provider event and its latest observed completion and standings state.
- **Final Results Version**: An immutable, Workspace-scoped publication version containing provider standings, resolved presentation, event metadata, verification status, and timestamps.
- **Standing Entry**: One provider-ranked entrant with placement, provider identity, tie information, presentation snapshot, and validation state.
- **Result Card Definition**: The single reusable nested design of bound/literal authoring elements used by freeform cards, linked instances, Results Group templates, PNG, and OBS.
- **Freeform Result Card**: An atomic canvas instance with its own transform and outer animation that references one Result Card definition.
- **Results Cards Scheduler**: A layout-neutral parent for freeform cards that controls member playback order, stagger, visibility retention, and looping.
- **Linked Card Instance**: A persisted lightweight placement instance with its own transform, z-index, standing selector, and optional animation override while sharing one Result Card definition.
- **Auto Sequence Runtime Instance**: An ephemeral card produced from the freeform stage card and scheduler time; it is never an authoring layer.
- **Results Group**: A template-based image/legacy-animation composition that consumes the shared Result Card and owns layout recipe, preview settings, and established sequence settings.
- **Card Variant**: An optional Results Group-only Champion, Podium, or Standard composition inheriting shared card styles with bounded overrides.
- **Layout Slot**: A placement-independent visual region defining a generated card's position, dimensions, and variant.
- **Sequence Cue**: A placement-independent reveal instruction with order, timing, state, and operator controls.
- **Media Output Profile**: Canvas dimensions, safe areas, background behavior, and export/live purpose.
- **Presentation Override**: An event-scoped organizer correction for display fields such as featured character, with an explicit path to update the reusable player profile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance testing, 100% of Final-labelled placements match the selected provider event and no active or awaiting-review event can be published as Final.
- **SC-002**: An organizer can select a completed event, customize the Champion Focus template, and export a Top 8 PNG in under five minutes without re-entering existing player or tournament data.
- **SC-003**: A designer can change one Result Card child and see the change in the freeform card, linked instances, Results Group preview, PNG, and OBS through one definition edit.
- **SC-004**: The layer list contains zero Auto Sequence or Results Group-generated runtime cards; only deliberately materialized linked cards appear.
- **SC-005**: A 2000 ms lifecycle with a 500 ms Delay Between Starts produces start times of 0, 500, 1000… ms and overlapping visible cards in automated and operator acceptance tests.
- **SC-006**: The same frozen results-version identifier is used by a static export and its corresponding live overlay, yielding identical placements and player presentation.
- **SC-007**: Missing optional media is reported before export or live operation, and 100% of affected entrants remain represented using deterministic fallbacks.
- **SC-008**: Top 8 and Top 16 outputs preserve every tied entrant at the cutoff in all acceptance datasets.
- **SC-009**: A restarted results overlay restores a safe, deterministic state without exposing another Workspace's data or advancing the sequence unexpectedly.
- **SC-010**: Unauthorized accounts cannot create, edit, export, take live, or control results media in all role and Workspace-isolation tests.
- **SC-011**: A designer can add a Result Card, edit and resize its internal fields, exit design mode, and move/animate the atomic card without consulting Results Group template settings.
- **SC-012**: Existing Results Group templates and established group animation output remain visually compatible after being rebased on the shared Result Card.

## Assumptions

- Final standings are selected per event; an aggregate tournament-wide ranking across unrelated events is outside the initial scope.
- Provider state remains authoritative for completion and placement, while aiTOB owns presentation, layout, animation, export, and broadcast state.
- The displayed character is the profile's featured character or an organizer-approved event override, not a claim about the character used in a specific match.
- Manual placement correction is outside the initial scope; discrepancies must be fixed at the provider and refreshed.
- The first static output format is PNG; additional image formats and video-file rendering may be added later.
- The editor remains desktop-oriented for detailed authoring; responsive operator controls may be used on smaller screens.
- Mock data is deterministic design-time content and never becomes tournament or player data.
- The approved reference image guides visual hierarchy only; its branding and protected artwork are not copied.
- A full arbitrary keyframe timeline comparable to dedicated motion-design software is outside scope; Result Cards deliberately reuse the editor's current Animation model plus group scheduling.

## Scope Boundaries

### Included

- Provider-authoritative event completion and standings readiness.
- Immutable results versions and presentation snapshots.
- Static social graphics based on reusable Results Groups or deliberately materialized freeform Result Cards.
- One shared editor-native Result Card design used by freeform, linked, template, export, and OBS consumers.
- Standard editor animation for freeform cards, overlapping Auto Sequence, linked card materialization, mock previews, and template layout/sequence settings.
- Dedicated post-tournament results overlays using the existing broadcast delivery boundary.
- Event-specific presentation corrections, including featured character.

### Excluded

- Local bracket calculation or inferred final placements.
- Editing provider-owned placements from the media designer.
- Claiming or tracking match-by-match character usage without a verified source.
- Full video rendering, audio timelines, arbitrary keyframe graphs, or a general-purpose motion-design replacement.
- Automatically publishing media to third-party social networks.
