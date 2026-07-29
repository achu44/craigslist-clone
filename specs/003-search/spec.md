# Spec 003: Posting Search

**Status:** Draft — awaiting review
**Depends on:** `specs/002-posting-lifecycle-ui/spec.md` (the `browse` view, its
`?category=` filter, and `templates/postings/browse.html`), and
`specs/001-domain-model/spec.md` (`Posting`, `Posting.objects.visible()`)

---

## 1. Purpose

Spec 002 gave browsers a way to page through every live posting on a Site, filtered only
by Category. Once a Site holds more than a screenful of postings, that is not a way to
find anything — the browser has to already know which Category the Poster chose.

This feature adds free-text search over a Site's live postings, so a browser can type
what they are looking for instead of guessing a Category. It was deferred explicitly by
spec 001 §7 ("full-text search and search indexing").

No new persisted domain state, no new page, and no new dependency.

---

## 2. User Stories

- As a browser, I want to type words into a search box and see only the live postings
  whose title or body matches, so that I can find something without knowing its Category.
- As a browser, I want my search to combine with the Category filter, so that I can
  narrow a broad term to one part of the Site.
- As a browser, I want the closest matches first, so that I do not have to read every
  result.
- As a browser, I want a search that matches nothing to say so plainly, so that I know
  the search ran and the Site simply has nothing matching.

---

## 3. Entities

No new persisted entities and no schema change. Search is computed at query time from
`Posting.title` and `Posting.body`, which already exist.

---

## 4. Functional Requirements

### 4.1 Ubiquitous

- The system shall accept a search term as the `q` query parameter on the existing browse
  URL (`/<site_slug>/browse/?q=...`); the system shall not add a separate search page.
- The system shall search only within the Site resolved from the URL path; the system
  shall not return postings belonging to another Site.
- The system shall search only postings in `Posting.objects.visible()`; the system shall
  not introduce a second definition of visibility.
- The system shall match against `Posting.title` and `Posting.body` only. Contact fields,
  `location_text`, Category names and Area names are not searched.
- The system shall use PostgreSQL full-text search through
  `django.contrib.postgres.search`; the system shall not add a search dependency and
  shall not use raw SQL.

### 4.2 Event-Driven

- WHEN a browser submits a non-empty `q` THE system SHALL return only visible postings for
  that Site whose title or body matches the term, ordered by descending relevance.
- WHEN two results have equal relevance THE system SHALL break the tie by
  `-published_at`, so that ordering is deterministic and stable across requests.
- WHEN a browser submits both `q` and `category` THE system SHALL apply both, returning
  only postings that satisfy both.
- WHEN a browser submits a `q` that matches no posting THE system SHALL render the browse
  page with an explicit empty-results message naming the term searched.

### 4.3 State-Driven

- WHILE `q` is absent or empty THE system SHALL behave exactly as spec 002's browse does:
  all visible postings for the Site, ordered by `-published_at`, optionally narrowed by
  `category`.
- WHILE a search is active THE system SHALL keep the submitted term visible in the search
  input, so that the browser can see and refine what was searched.

### 4.4 Unwanted Behavior

- IF `q` consists only of whitespace THEN THE system SHALL treat it as absent rather than
  running an empty search.
- IF `q` contains PostgreSQL full-text operators (`&`, `|`, `!`, `:*`, parentheses) THEN
  THE system SHALL treat them as literal user text rather than as query syntax, and shall
  not return a 500.
- IF `q` exceeds 200 characters THEN THE system SHALL truncate it to 200 characters before
  searching rather than rejecting the request.
- IF a search term matches a posting that is not `ACTIVE` THEN THE system SHALL NOT return
  it, in any status, including one whose title matches exactly.

### 4.5 Optional Features

- WHERE a search returns results THE system MAY display the number of matches. Result
  snippets and match highlighting are out of scope (§6).

---

## 5. Non-Functional Requirements

- Search shall be one database query, composed onto the existing browse queryset rather
  than issued separately and merged in Python.
- Search shall remain legible to a reviewer in one pass (CLAUDE.md §1): the query is built
  from `SearchVector`/`SearchQuery`/`SearchRank` with no hand-written tsquery strings.
- Search shall degrade to plain browse behavior with JavaScript disabled — the search box
  is an ordinary `GET` form, not an HTMX-only control.

---

## 6. Out of Scope

Explicitly not part of this feature:

- A stored `SearchVectorField`, a `GinIndex`, or any denormalized index (§8.2)
- Result snippets, match highlighting, and "did you mean" suggestions
- Stemming or dictionary configuration beyond PostgreSQL's default `english`
- Searching across Sites
- Searching Category names, Area names, or any contact field
- Faceted counts, saved searches, and search-result email alerts
- Any ranking signal beyond text relevance — CLAUDE.md §11 bars recommendation or ranking
  algorithms beyond deterministic sort and text relevance

---

## 7. Acceptance Verification

This feature is complete when:

1. Every requirement in §4 has at least one test asserting it, using Django's test client
   against the browse URL.
2. Every case in §4.4 has a test — in particular, a posting in each of the six non-ACTIVE
   statuses whose title matches the term exactly, asserted absent from results.
3. `uv run pytest` passes and coverage on `apps/` remains ≥ 80%.
4. `uv run ruff check .` and `uv run ruff format --check .` pass, and
   `uv run python manage.py makemigrations --check` reports no drift — this feature must
   produce no migration.

---

## 8. Open Decisions

Resolved with the user before this spec was written:

1. **Search is a `q` parameter on browse, not its own page.** Browse already owns the
   listing template, the Category filter, and the visible-postings queryset; a separate
   `/search/` view would duplicate all three to render the same list of postings. The
   filters compose naturally as query parameters.
2. **No stored search vector.** `SearchVector` is computed per query. A
   `SearchVectorField` with a `GinIndex` is measurably faster on large tables, but it adds
   a column, a migration, and a save-time sync path that can silently go stale — an
   abstraction ahead of a demonstrated need, against CLAUDE.md §1. §6 records it as the
   intended upgrade once row counts justify it, and the change is confined to one service
   function.
3. **Search is scoped to one Site.** Everything in spec 002 resolves a Site from the URL
   path; a cross-site search would need a URL outside `/<site_slug>/` and would contradict
   that. Multi-site search is not a stated goal.
