# Tasks 003: Posting Search

**Implements:** `specs/003-search/spec.md` per `specs/003-search/plan.md`

Tasks are ordered by dependency. Each is atomic and independently verifiable; run the
listed verification before moving to the next task. Cite this file
(`refs specs/003-search/tasks.md`) in commit bodies alongside the spec per CLAUDE.md §9.

---

## Phase A — App Scaffolding

- [x] **T001** Create `apps/search/` with `__init__.py` and `apps.py`
  (`AppConfig.name = "apps.search"`). No `models.py`, no `migrations/` (plan.md §2).
  **Verify:** `uv run python manage.py check` runs without `ModuleNotFoundError`.

- [x] **T002** Add `"apps.search"` to `INSTALLED_APPS` in `config/settings.py`.
  Do **not** add `django.contrib.postgres` (plan.md §6).
  **Verify:** `uv run python manage.py check` passes; `uv run python manage.py makemigrations --check`
  still reports no changes.

---

## Phase B — Search Service (plan.md §3)

- [x] **T003** `apps/search/services.py`: `normalize_query(raw)` — returns `""` for
  `None`, empty, or whitespace-only input; strips surrounding whitespace; truncates to
  `MAX_QUERY_LENGTH = 200`.
  **Verify:** unit tests in `tests/search/test_services.py` for each of those four cases;
  no database needed.

- [x] **T004** `apps/search/services.py`: `search_postings(postings, term)` exactly as
  specified in plan.md §3 — `SearchVector("title", "body")`, `SearchQuery(...,
  search_type="plain")`, `SearchRank`, ordered `-rank, -published_at`.
  **Verify:** test asserts a term matching a title returns that posting; a term matching
  only a body returns that posting; a term matching neither returns nothing.

- [x] **T005** `search_postings` returns its input queryset **unchanged** for an empty
  term — no annotation, no re-ordering (plan.md §3, spec.md §4.3).
  **Verify:** test asserts `search_postings(qs, "") is qs` or that the two produce
  identical results in identical order.

- [x] **T006** Ranking: a posting matching in the title outranks one matching only in the
  body, and equal-rank results are tie-broken by `-published_at`.
  **Verify:** test builds three postings and asserts the exact result order; test asserts
  two equally-ranked postings come back newest-first on repeated evaluation.

---

## Phase C — Visibility and Hostile Input (spec.md §4.4)

These are the tests that justify the feature; do not fold them into Phase B.

- [x] **T007** Search never returns a non-visible posting.
  **Verify:** one test creating a posting in **each** of DRAFT, PENDING, EXPIRED, DELETED,
  HIDDEN and BLOCKED whose title is exactly the search term, asserting each is absent —
  six assertions, not one parametrized happy path.

- [x] **T008** Search never crosses a Site boundary.
  **Verify:** test creates a matching ACTIVE posting on a second Site and asserts it is
  absent from the first Site's results.

- [x] **T009** Full-text operator characters are treated as literal text.
  **Verify:** test searches `desk & chair | !sofa` and `(unbalanced` and asserts a normal
  empty-or-matching result rather than a raised exception.

---

## Phase D — Browse Integration (plan.md §4)

- [x] **T010** `apps/postings/views.py`: `browse()` reads `?q=`, normalizes it, applies
  `search_postings` after the site and category filters, and adds `term` to the context.
  **Verify:** test asserts `?q=` narrows results; test asserts `?q=` and `?category=`
  together apply both; test asserts an absent/blank `q` reproduces spec 002's browse
  ordering exactly.

- [x] **T011** `templates/postings/browse.html`: plain `GET` search form preserving the
  selected category in a hidden field, echoing the submitted term back into the input, and
  a search-aware empty-results message (plan.md §5). No HTMX.
  **Verify:** test asserts the submitted term appears in the rendered input; test asserts
  the no-match page names the term searched; test asserts searching while a category is
  selected keeps both parameters on the follow-up request.

---

## Phase E — Acceptance Verification (spec.md §7)

- [x] **T012** Run the full suite and report status:
  - `uv run python manage.py check`
  - `uv run pytest`
  - `uv run pytest --cov=apps --cov-report=term-missing` (≥ 80% on `apps/`)
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run python manage.py makemigrations --check` — must report **no changes**; a
    migration here means something was modeled that spec.md §3 says should not be
  - Manual: `seed_dev_data`, create two postings with distinct words, search for one and
    confirm only it returns, then combine the search with the category filter
  - Manual pass: confirm every spec.md §4 requirement is covered by at least one test name
    findable by `grep -r` in `tests/search/` and `tests/postings/test_views_browse.py`
