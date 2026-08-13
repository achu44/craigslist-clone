# Plan 003: Posting Search

**Implements:** `specs/003-search/spec.md`

---

## 1. Approach

Search is a queryset transform, not a subsystem. One function takes the queryset browse
already builds and returns a narrowed, re-ordered version of it. The browse view gains a
few lines; nothing else in the posting layer changes.

The whole feature is:

```python
Posting.objects.visible().filter(site=site)      # unchanged, from spec 002
    |> search_postings(term)                     # new: annotate + filter + order
```

No model change, no migration, no new dependency. `django.contrib.postgres.search` ships
with Django and PostgreSQL 16 is already the sole datastore (CLAUDE.md §2), so the
capability is present without adding anything — which the dependency policy requires us to
prefer.

---

## 2. App Breakdown

CLAUDE.md §4 reserves `apps/search/` for exactly this, so the query-building lives there
rather than in `apps/postings`:

```
apps/search/
├── __init__.py
├── apps.py          # AppConfig.name = "apps.search"
└── services.py      # search_postings()
```

The app has no models and no migrations. It is still registered in `INSTALLED_APPS` for
consistency with its four siblings and so its tests resolve the same way.

`apps/postings/views.py` imports from it. The dependency direction is
`postings → search`, never the reverse: `search` knows how to filter a queryset of
postings, and knows nothing about views, sites, or request handling.

---

## 3. The Search Service (`apps/search/services.py`)

```python
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import QuerySet

MAX_QUERY_LENGTH = 200
SEARCH_CONFIG = "english"


def normalize_query(raw: str | None) -> str:
    """Whitespace-only input is not a search (spec §4.4); over-long input is trimmed."""
    if not raw:
        return ""
    return raw.strip()[:MAX_QUERY_LENGTH]


def search_postings(postings: QuerySet, term: str) -> QuerySet:
    if not term:
        return postings
    vector = SearchVector("title", weight="A", config=SEARCH_CONFIG) + SearchVector(
        "body", weight="B", config=SEARCH_CONFIG
    )
    query = SearchQuery(term, config=SEARCH_CONFIG, search_type="plain")
    return (
        postings.annotate(search=vector, rank=SearchRank(vector, query))
        .filter(search=query)
        .order_by("-rank", "-published_at")
    )
```

Four decisions worth stating, because each maps onto a requirement:

- **Weighted vector (`title` = A, `body` = B).** *Amended during implementation, with user
  approval.* This section originally specified a single unweighted
  `SearchVector("title", "body")`, which contradicted tasks.md T006's requirement that a
  title match outrank a body-only match: one unweighted vector puts both fields at
  PostgreSQL's default weight `D`, scoring them identically. Measured for the term
  `couch`, unweighted gave title `0.060793` and body `0.060793` — a tie, leaving the
  `-published_at` fallback to decide relevance order. Weighted gives title `0.607927` and
  body `0.243171`. Adding the weights costs nothing: same single query, still no
  migration, still no dependency.
- **`search_type="plain"`** routes through `plainto_tsquery`, which treats `&`, `|`, `!`
  and parentheses as ordinary words rather than operators. That is what satisfies spec
  §4.4's "no 500 on operator characters" without any escaping code of our own. Do not
  switch to `raw` or `websearch` without revisiting that requirement.
- **`-rank, -published_at`** — `SearchRank` alone leaves ties in database order, which is
  not stable between requests. The secondary key makes the ordering deterministic, which
  spec §4.2 requires and is the only kind of ordering CLAUDE.md §11 permits.
- **`normalize_query` is separate from `search_postings`** so the view can use the
  normalized term for both the query and what it echoes back into the search box, without
  normalizing twice or echoing something different from what was searched.

`search_postings` returns its input untouched for an empty term, so the browse view has
no branch of its own — spec §4.3's "behave exactly as browse does" falls out rather than
being re-implemented.

---

## 4. Browse View Changes (`apps/postings/views.py`)

`browse()` is the only view that changes:

```python
term = normalize_query(request.GET.get("q"))
postings = search_postings(postings, term)
```

applied **after** the existing `site` and `category` filters, so all three compose
(spec §4.2). The `-published_at` ordering already set by spec 002 is replaced by
`search_postings`' ordering only when a term is present.

`term` is added to the template context. Nothing else in the view moves.

**Query count:** still one query for the listing. `select_related("category", "area")`
stays as-is.

---

## 5. Template Changes (`templates/postings/browse.html`)

A plain `GET` form above the listing, containing the search input and preserving the
current category selection as a hidden field so the two filters do not clobber each other:

```html
<form method="get" action=".">
  <input type="search" name="q" value="{{ term }}" placeholder="Search postings">
  {% if selected_category %}<input type="hidden" name="category" value="{{ selected_category }}">{% endif %}
  <button type="submit">Search</button>
</form>
```

No HTMX. Spec 002 §4.1 limits HTMX to isolated enhancements, and a search form that
navigates is the framework default — adding a live-search swap here would be exactly the
"wholesale fragment-swapping" that spec forbids.

The empty-results branch becomes conditional on whether a search is active:

```html
{% empty %}
  {% if term %}<p>No postings match "{{ term }}".</p>
  {% else %}<p>No postings yet.</p>{% endif %}
```

---

## 6. Settings

Add `"apps.search"` to `INSTALLED_APPS`. Nothing else. In particular
`django.contrib.postgres` does **not** need to be installed — `SearchVector`,
`SearchQuery` and `SearchRank` are query expressions that work without it. Adding it would
only be needed for its model fields, form fields and lookups, none of which this feature
uses.

---

## 7. Testing

Tests go in `tests/search/test_services.py` (the service, against the queryset directly)
and `tests/postings/test_views_browse.py` (the `?q=` behavior end-to-end, alongside the
existing `?category=` tests it composes with).

Reusing `tests/factories.py` from spec 001 — `make_posting(status=..., title=..., body=...)`
already takes the overrides these tests need, so no new factory.

The coverage that matters most, per spec §7.2: a posting in **each** of the six non-ACTIVE
statuses, whose title is exactly the search term, asserted absent. A search that bypasses
`visible()` would pass every other test in the suite and fail only these.

Also required: an operator-soup term (`"desk & chair | !sofa"`) asserting a 200 rather
than a 500, and a >200-character term asserting truncation rather than rejection.

---

## 8. Verification

- `uv run pytest`
- `uv run pytest --cov=apps --cov-report=term-missing` (≥ 80% on `apps/`)
- `uv run ruff check .` and `uv run ruff format --check .`
- `uv run python manage.py makemigrations --check` — **must report no changes.** This
  feature adds an app with no models; a migration appearing here means something was
  modeled that the spec says should not be.
- Manual: `seed_dev_data`, create two postings with distinct words, search for one and
  confirm only it comes back, then combine with the category filter.
