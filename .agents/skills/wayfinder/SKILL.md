---
name: wayfinder
description: "跨 Session 決策地圖：當任務太大、一個 Session 裝不下時，建立決策地圖逐一解決，直到路線清晰。Plan a huge chunk of work as a shared map of decision tickets, resolved one at a time until the way is clear."
---

A loose idea has arrived, too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding is about finding that way, not charging at the destination. This skill charts the way as a **shared map** on the repo's issue tracker, then works its **decision tickets** (questions whose resolution is a decision, not slices of a build to execute) one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting: it shapes every ticket. It might be a spec to hand off and iterate on, a decision to lock before planning starts, or a change made in place like a data-structure migration. The map is domain-agnostic: engineering work, course content, whatever fits the shape.

## Plan, don't do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear, with nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off. An effort can override this in its **Notes**, carrying execution into the map itself, but absent that, produce decisions, not deliverables.

## Refer by name

Every map and ticket is an issue, so it has a **name**: its title. In everything the human reads (narration, the map's Decisions-so-far), refer to it by that name, never by a bare id, number, or slug. A wall of `#42, #43, #44` is illegible; names read at a glance.

## The Map

The map is a single file on this repo's local issue tracker (`.scratch/<effort>/map.md`), the canonical artifact. Its tickets are child files under `.scratch/<effort>/issues/`.

The map is an **index**, not a store. It lists the decisions made and points at the tickets that hold their detail; a decision lives in exactly one place, its ticket, so the map never restates it, only gists it and links.

### The map body

The whole map at low resolution, loaded once per session. Open tickets are **not** listed: they are open child files, found by scanning.

```markdown
## Destination

<what reaching the end of this map looks like: the spec, decision, or change this effort is finding its way to. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [<closed ticket title>](link): <one-line gist of the answer>

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; closed, never graduates -->
```

### Tickets

Each ticket is a **child file** of the map; its body is the question, sized to one 100K token agent session:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

Each ticket carries a `Type:` line, one of `research`, `prototype`, `grilling`, `task` (see [Ticket Types](#ticket-types)).

A session **claims** a ticket by setting `Status: claimed`, **first**, before any work.

Blocking uses a `Blocked by: NN, NN` line near the top. A ticket is **unblocked** when every file it lists is `resolved`; the **frontier** is the open, unblocked, unclaimed children.

## Ticket Types

Every ticket is either **HITL** (human in the loop, worked _with_ a human who speaks for themselves) or **AFK**, driven by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it.

- **Research** (AFK): Reading documentation, third-party APIs, or local resources. Resolved by a subagent that calls the Skill tool with "research". Use when knowledge outside the current working directory is required.
- **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough, concrete artifact. Call the Skill tool with "prototype". Use when "how should it look" or "how should it behave" is the key question.
- **Grilling** (HITL): Conversation. The default case. Always call the Skill tool twice, for "grilling" and "domain-modeling".
- **Task** (HITL or AFK): Manual work that must happen before a _decision_ can be made.

## Fog of war

The map is _deliberately_ incomplete: don't chart what you can't yet see. Beyond the live tickets lies the **fog of war**: the dim view of decisions and investigations you can tell are coming but can't yet pin down, because they hang on questions still open. Resolving a ticket clears the fog ahead of it, graduating whatever's now specifiable into fresh tickets, one at a time, until the way to the destination is clear and no tickets remain.

The map's **Not yet specified** section is where that dim view is written down. It's the undiscovered frontier _toward_ the destination.

**Fog or ticket?** The test is whether you can state the question precisely now, _not_ whether you can answer it now.

## Out of scope

Fog only ever gathers _toward_ the destination. The destination fixes the scope, so work beyond it is **out of scope**. It gets its own **Out of scope** section on the map.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session**, with the exception of research tickets.

### Chart the map

User invokes with a loose idea.

1. **Name the destination.** Call the Skill tool twice, for "grilling" and "domain-modeling", to pin down what this map is finding its way to.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog**, you don't need a map. Stop and ask the user how they'd like to proceed.
3. **Create the map** (`.scratch/<effort>/map.md`): Destination and Notes filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**.
4. **Create the tickets** as child files under `.scratch/<effort>/issues/`, then wire blocking edges.
5. **Fire the research subagents.** For each `research` ticket, spin up a subagent to resolve it in parallel.
6. Stop: charting is one session's work; it hand-resolves nothing.

### Work through the map

User invokes with a map (path or name). A ticket is **optional**: without one, you pick the next decision, not the user.

1. Load the **map**: the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order. **Claim it**.
3. Resolve it. **Zoom as needed**: fetch the full body of any related or closed ticket on demand.
4. Record the resolution: append the answer under an `## Answer` heading, set `Status: resolved`, and append a context pointer to the map's Decisions-so-far.
5. Add newly-surfaced tickets; graduate any fog the answer has made specifiable.
