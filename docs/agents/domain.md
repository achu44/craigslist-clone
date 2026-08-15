# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CLAUDE.md` §3** — the binding term table. Always read this one; it already exists.
- **`CONTEXT.md`** at the repo root, if it exists.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If `CONTEXT.md` or `docs/adr/` don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This is a **single-context** repo — one Django project, and CLAUDE.md §11 makes that permanent.

```
/
├── CLAUDE.md          ← §3 is the binding glossary
├── CONTEXT.md         ← supplements §3; created lazily
├── docs/adr/
│   ├── 0001-....md
│   └── 0002-....md
└── apps/              ← Django apps: geo, taxonomy, postings, search, moderation
```

Note this project uses `apps/`, not `src/`. There is no `CONTEXT-MAP.md` and no per-context `docs/adr/`.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the glossary. Don't drift to synonyms the glossary explicitly avoids.

**CLAUDE.md §3 is the authority.** It defines Posting, Poster, Site, Area, Channel, Category, Manage token, Flag, Renew and Repost, each with an explicit "do NOT call it" column. Where `CONTEXT.md` and §3 disagree, §3 wins — `CONTEXT.md` supplements it with terms §3 doesn't yet cover, it does not override it.

Two of these are a distinction, not a preference: **Renew** is the same Posting with a new expiry; **Repost** is a new Posting with a new identifier. Conflating them is a domain error.

If the concept you need isn't in either document yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_

## ADRs cannot overrule the constitution

CLAUDE.md §2 (technology stack) and §11 (explicit non-goals) are constitutional, not architectural. An ADR proposing Celery, React, a second datastore, microservices, or i18n is not an ADR — it is a **constitution amendment**, and it must be raised as one against CLAUDE.md rather than recorded in `docs/adr/`.
