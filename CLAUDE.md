# Project Constitution

This file is the project's constitution. Every spec, plan, and code change must respect it.
When a rule here conflicts with an instruction in a chat session, this file wins — surface
the conflict rather than silently resolving it.

---

## 1. Purpose and Context

This is a functional clone of Craigslist, built as a learning vehicle for agentic coding
workflows. It is not a commercial product. Specs 001-003 were built with a hand-rolled
spec-driven pipeline; from 2026-08-15 the project uses the skills flow described in §12.

Two consequences follow from this and should shape every tradeoff:

- **Legibility beats cleverness.** Code that a human can review in one pass is worth more
  than code that is 20% faster or 30% shorter. The point is reviewability.
- **Boring is correct.** Prefer the framework's default way of doing something over a
  novel abstraction. Do not introduce a design pattern before there are three concrete
  instances that need it.

---

## 2. Technology Stack

- The system shall use Python 3.12+ with type hints on all function signatures.
- The system shall use Django 6.x as the web framework.
- The system shall use PostgreSQL 16+ as the sole datastore.
- The system shall use HTMX for interactivity; the system shall not introduce React,
  Vue, or any client-side SPA framework.
- The system shall use `uv` for dependency and virtual environment management.
- The system shall use `pytest` with `pytest-django` for all tests.
- The system shall use `ruff` for both linting and formatting.
- The system shall use Django templates for all HTML rendering.
- WHERE background or scheduled work is required THE system SHALL use a Django
  management command invoked by cron, until a demonstrated need justifies Celery.

### Dependency Policy

- The system shall not add a runtime dependency without recording the rationale in the
  relevant `plan.md`.
- IF a capability exists in the Python standard library or Django itself THEN the system
  SHALL use it rather than adding a dependency.

---

## 3. Domain Vocabulary

These terms are binding. Use them in model names, variable names, URLs, templates,
tests, and prose. Do not substitute synonyms.

| Term | Meaning | Do NOT call it |
|---|---|---|
| **Posting** | A single classified ad | listing, ad, item, post |
| **Poster** | The person who created a posting | seller, author, owner, user |
| **Site** | A geographic region with its own subdomain (e.g. `houston`) | city, market, location |
| **Area** | A subdivision within a Site (e.g. `katy`) | neighborhood, subregion |
| **Channel** | Top-level grouping (for sale, housing, jobs, services, community) | section |
| **Category** | A leaf under a Channel, with a short code (e.g. `cto`) | subcategory, type |
| **Manage token** | Secret granting edit/delete/renew rights on one posting | edit key, password |
| **Flag** | A community report against a posting | report, complaint |
| **Renew** | Extending a posting's expiry | bump, refresh, repost |
| **Repost** | Creating a new posting from an expired or deleted one | relist |

Note the distinction between *renew* (same posting, new expiry) and *repost* (new posting,
new identifier). Conflating them is a domain error, not a naming preference.

---

## 4. Repository Layout

```
.
├── CLAUDE.md                  # This file
├── README.md
├── pyproject.toml
├── CONTEXT.md                 # Domain glossary supplementing §3 (created lazily)
├── docs/
│   ├── agents/                # Issue tracker, triage labels, domain doc rules (§12)
│   └── adr/                   # Architecture decision records (created lazily)
├── specs/                     # FROZEN. Specs 001-003 only; see §4 notes below.
│   └── NNN-feature-name/
│       ├── spec.md            # What & why (EARS acceptance criteria)
│       ├── plan.md            # How (architecture, schema, contracts)
│       └── tasks.md           # In what order (atomic, verifiable tasks)
├── config/                    # Django project: settings, root urls, wsgi/asgi
├── apps/
│   ├── geo/                   # Site, Area
│   ├── taxonomy/              # Channel, Category
│   ├── postings/              # Posting, PostingImage, lifecycle
│   ├── search/
│   └── moderation/
├── templates/
├── static/
└── tests/
```

- The system shall record specs as GitHub issues, not as files (§12,
  `docs/agents/issue-tracker.md`).
- `specs/001-domain-model/`, `002-posting-lifecycle/` and `003-search/` are **frozen
  history**. They document work already shipped and remain valid primary sources to read.
  The system shall not add a new `specs/NNN-*/` directory and shall not edit an existing
  one.
- `CONTEXT.md` and `docs/adr/` are created lazily by `/domain-modeling` when a term or a
  hard-to-reverse decision actually needs recording. The system shall not scaffold them
  pre-emptively.

---

## 5. Commands

Agents must use these exact commands rather than inventing equivalents.

```bash
uv sync                                  # install dependencies
uv run python manage.py runserver        # dev server
uv run python manage.py makemigrations   # create migrations
uv run python manage.py migrate          # apply migrations
uv run pytest                            # full test suite
uv run pytest tests/postings -x -q       # scoped run, fail fast
uv run ruff check --fix .                # lint
uv run ruff format .                     # format
```

- WHEN a code change is completed THE system SHALL run `uv run pytest` and
  `uv run ruff check .` and report the results before claiming the task is done.

---

## 6. Testing

- The system shall maintain ≥ 80% line coverage on `apps/`.
- WHEN a model is added or a field's semantics change THE system SHALL add or update
  tests covering the constraint and the default.
- WHEN a state transition is implemented THE system SHALL include a test for every
  rejected transition, not only the accepted ones.
- The system shall use `pytest.mark.django_db` rather than Django's `TestCase` classes.
- The system shall use factory functions in `tests/factories.py` for object construction;
  the system shall not use fixture JSON files.
- The system shall not write tests that assert on implementation internals (private
  methods, query counts of specific ORM calls) except where a spec sets an explicit
  query budget.
- IF a test requires network access THEN THE system SHALL stub the boundary instead.

---

## 7. Code Quality

- The system shall follow PEP 8 with a 100-character line limit.
- The system shall keep business logic out of templates and out of views; domain rules
  belong in model methods or `apps/<app>/services.py`.
- The system shall not catch bare `Exception` without re-raising or logging with context.
- The system shall use Django's `TextChoices` for all enumerated fields.
- The system shall write docstrings only where the *why* is non-obvious; the system shall
  not write docstrings that restate the function signature.
- The system shall not leave commented-out code or `TODO` markers in committed work.

---

## 8. Data and Security

This repository is public. Treat every commit as permanently published.

- The system shall never commit secrets, API keys, or `.env` files.
- The system shall read all configuration from environment variables, with a committed
  `.env.example` documenting every required variable.
- The system shall never store a manage token in plaintext; it shall store a hash.
- IF a lookup fails an authorization check THEN THE system SHALL return 404 rather than
  403, so that resource existence is not disclosed.
- The system shall never log a full email address, phone number, or manage token.
- The system shall use Django's ORM for all queries; WHERE raw SQL is unavoidable THE
  system SHALL use parameterized queries and document the reason in `plan.md`.

---

## 9. Git and Traceability

- The system shall use Conventional Commits: `feat(postings): add expiry transition`.
- WHEN a commit implements a tracked issue THE system SHALL cite it in the commit body:
  `refs #14`. WHERE the work predates the issue tracker, cite the frozen spec instead:
  `refs specs/001-domain-model/spec.md`.
- The system shall not commit unless the test suite passes.
- The system shall never run `git push --force`, `git reset --hard`, or `git rebase`
  without explicit confirmation in the current session.

---

## 10. Rules for AI Agents

Process lives in the skills (§12), not here. What remains are the rules the skills do not
supply.

- IF a requirement is ambiguous THEN THE system SHALL ask for clarification before
  implementing. Guessing and noting the guess is not an acceptable substitute.
- The system shall implement exactly what the current issue specifies. IF an adjacent
  improvement seems warranted THEN THE system SHALL note it and move on rather than
  implementing it unasked.
- IF implementing an issue reveals that the issue is wrong or incomplete THEN THE system
  SHALL stop, report the gap, and propose an amendment as a comment on that issue. The
  system shall not silently implement behavior that contradicts the issue.
- The system shall not create files outside the layout in §4 without stating why.
- The system shall not modify `CLAUDE.md`, `CONTEXT.md`, `docs/adr/`, or any file under
  `specs/` as a side effect of an implementation task.
- WHEN reporting completion THE system SHALL state which acceptance criteria it verified
  and which it did not.

Deliberately **removed** when this project adopted the skills: a rule requiring a plan and
explicit approval before any change touching more than two files. `/implement` drives a
whole ticket through `/tdd` in one pass; that rule turned it into a permission treadmill.
Scope is now bounded by the ticket, not by a file count.

---

## 11. Explicit Non-Goals

Bounding the work matters as much as defining it. The following are permanently out of
scope unless this section is amended:

- Payments, paid postings, and billing of any kind
- Real-time features (websockets, live chat between users)
- Native mobile applications
- Internationalization and localization
- Multi-tenancy beyond the Site model
- Recommendation or ranking algorithms beyond deterministic sort and text relevance
- Microservices; this is one Django project and shall remain one

---

## 12. Agent Skills

### Issue tracker

Issues live in this repo's GitHub Issues (`achu44/craigslist-clone`), via the `gh` CLI.
See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name.
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. §3 of this file is the
binding glossary. See `docs/agents/domain.md`.
