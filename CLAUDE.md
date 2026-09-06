# lotus-render — where this repository's truth lives

This file holds no repository facts on purpose. It routes to the documents that own
them. The last time it carried its own copies it went stale invisibly: it stated that
template `v1` was `development` long after `v1` and `v2` were published, and nothing
could catch that, because a copy has no source to disagree with.

`AGENTS.md` is the authority on the reading order and applies to every agent. This file
is the Claude-side entry point to the same guidance, not a second set of rules. Where
the two ever disagree, `AGENTS.md` wins and this file is the bug.

## Read first (small, mandatory)

1. `AGENTS.md` — operating contract and instruction precedence. Synchronized across the
   estate from `lotus-platform`; do not hand-edit it here. Run the platform sync in this
   repository only, never with `-AllRepoRoots`, which writes into twelve working trees.
2. `REPOSITORY-ENGINEERING-CONTEXT.md` — THIS repository's truth: role, ownership
   boundaries, architecture, repo-native commands, CI expectations, known constraints,
   and the working practices that cost us something to learn. Repo-scoped practice
   belongs there, in the section that names itself as practice.
3. `README.md` — product front door: what the service is and where to go next.

That is the starting set. Everything below is read only when the task calls for it.

## Read when the task calls for it

- Shared Lotus standards and engineering conventions: the `lotus-platform` context set
  (quickstart, engineering context, reference map). Load the reference map when you need
  to find which document owns a subject.
- How work should be executed rather than what is true here: the platform procedural
  memory index and skill routing map.
- Template, contract or rendering detail: `wiki/` for the published surfaces, `docs/` for
  standards and runbooks, and the template manifests for publication state — the
  manifests are the source, never a sentence about them.
- Deployment, alerting or incident response: the service operations runbook under
  `docs/runbooks/`.

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
