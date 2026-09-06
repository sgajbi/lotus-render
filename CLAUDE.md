# lotus-render — where this repository's truth lives

This file holds no repository facts on purpose. It routes to the documents that own
them. The last time it carried its own copies it went stale invisibly: it stated that
template `v1` was `development` long after `v1` and `v2` were published, and nothing
could catch that, because a copy has no source to disagree with.

`AGENTS.md` is the authority on the reading order and applies to every agent. This file
is the Claude-side entry point to the same guidance, not a second set of rules. Where
the two ever disagree, `AGENTS.md` wins and this file is the bug.

## Reading order

**`AGENTS.md` defines it. Read it there.** This file deliberately does not restate the
order, because a second copy is how a mandatory item quietly becomes an optional one — an
earlier version of this file listed three documents as "the starting set" and pushed the
platform quickstart, engineering context and reference map into an optional section, when
the contract makes them mandatory.

Everything `AGENTS.md` lists is mandatory as written, including the platform context set.
If that set should be smaller, propose the reduction centrally in `lotus-platform` rather
than shrinking it here — a repository cannot opt itself out of a synchronized contract.

## What this repository adds

Read these when the task reaches them; they are additional to the contract's order, never
a substitute for it:

- **Template, contract or rendering detail** — `wiki/` for the published surfaces, `docs/`
  for standards and runbooks. Template publication state comes from the manifests
  themselves, never from a sentence about them.
- **Deployment, alerting or incident response** — `docs/runbooks/service-operations.md`.
- **Why a thing is shown** — that decision belongs to `lotus-report`. This repository reads
  postures and never infers them.

## Locating shared context without a sibling checkout

The reading order names shared documents by paths such as
`lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`. That form assumes `lotus-platform`
is checked out beside this repository, which is the local workspace convention and not a
guarantee.

Without that checkout, read the same files at their canonical location:
`https://github.com/sgajbi/lotus-platform/blob/main/context/<FILENAME>`.

Verified on `lotus-platform` `origin/main`: `LOTUS-QUICKSTART-CONTEXT.md`,
`LOTUS-ENGINEERING-CONTEXT.md`, `CONTEXT-REFERENCE-MAP.md`,
`PROCEDURAL-MEMORY-INDEX.md`, `LOTUS-SKILL-ROUTING-MAP.md` and
`Repository-Engineering-Context-Contract.md` all exist under `context/`. Skills are
routed by the skill routing map rather than by a path in this file, so consult that map
rather than assuming a skills directory location.

## Tool differences

`AGENTS.md` and `CLAUDE.md` point at the same authoritative guidance and neither
overrides the other. The only genuine difference is discovery: the Claude runtime loads
`CLAUDE.md` automatically, while `AGENTS.md` is loaded because the reading order names
it. Read `AGENTS.md` explicitly; do not rely on this file having summarized it.

## The rule for this file

If you are about to state a fact here — a version, a gate, a ceiling, a posture, a
command — put it in `REPOSITORY-ENGINEERING-CONTEXT.md` and link to it instead. A router
that starts holding facts becomes a second source of truth, and the second source is the
one that goes stale without anyone noticing.
