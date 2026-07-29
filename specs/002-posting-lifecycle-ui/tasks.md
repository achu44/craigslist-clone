# Tasks 002: Posting Lifecycle UI

**Implements:** `specs/002-posting-lifecycle-ui/spec.md` per `specs/002-posting-lifecycle-ui/plan.md`

Tasks are ordered by dependency. Each is atomic and independently verifiable; run the
listed verification before moving to the next task. Cite this file
(`refs specs/002-posting-lifecycle-ui/tasks.md`) in commit bodies alongside the spec per
CLAUDE.md §9.

---

## Phase A — Settings & Project Wiring (plan.md §1)

- [ ] **T001** Add `django_htmx` to `INSTALLED_APPS` and `django_htmx.middleware.HtmxMiddleware`
  to `MIDDLEWARE` in `config/settings.py`.
  **Verify:** `uv run python manage.py check` passes with no missing-app/middleware errors.

- [ ] **T002** Set `TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]` and add
  `STATICFILES_DIRS = [BASE_DIR / "static"]` in `config/settings.py`.
  **Verify:** `uv run python manage.py check` passes; `uv run python manage.py collectstatic --dry-run`
  runs without error once T012 adds a static file.

- [ ] **T003** Create `apps/postings/urls.py` (empty `urlpatterns = []`, `app_name = "postings"`
  placeholder) and wire it into `config/urls.py` via `path("", include("apps.postings.urls"))`.
  **Verify:** `uv run python manage.py check` passes.

---

## Phase B — Base Template & Static Assets

- [ ] **T004** Add a minimal `static/css/base.css`. No htmx file is vendored into this
  repository: `django-htmx` already ships the bundle at
  `django_htmx/static/django_htmx/htmx-2.min.js` (plan.md §5), so there is nothing to
  download.
  **Verify:** `static/css/base.css` exists; `uv run python manage.py collectstatic --dry-run`
  lists it, and `django_htmx/htmx-2.min.js` resolves via
  `django.contrib.staticfiles.finders.find`.

- [ ] **T005** `templates/base.html`: shared layout loading `static/css/base.css` and
  `django_htmx/htmx-2.min.js`, with a `{% block content %}`.
  **Verify:** `uv run python manage.py check` passes (template syntax is validated by
  Django's system checks only loosely — real verification comes when the first view
  renders it in T009).

---

## Phase C — Forms (plan.md §3)

- [ ] **T006** `apps/postings/forms.py`: `PostingCreateForm` exactly as specified in
  plan.md §3 — leaf-only category queryset (`annotate(child_count=Count("children")).filter(child_count=0)`),
  area field required/removed based on `site.areas.exists()`.
  **Verify:** unit test — form with a site that has areas requires `area`; a site with no
  areas has no `area` field at all; category queryset excludes a category with children.

---

## Phase D — Browse & Detail Views (plan.md §4, spec.md §4.2)

- [ ] **T007** `apps/postings/views.py`: `browse(request, site_slug)` — 404 for an
  unknown/inactive site slug, lists `Posting.objects.visible()` filtered to the site,
  optional `?category=` filter, ordered newest-published-first.
  **Verify:** test asserts DRAFT/PENDING/EXPIRED/DELETED/HIDDEN/BLOCKED postings never
  appear; test asserts the category filter narrows results; test asserts 404 for a bad
  site slug.

- [ ] **T008** `detail(request, site_slug, public_id)` — 404 unless the posting is in
  `Posting.objects.visible()` for that site.
  **Verify:** test asserts an ACTIVE posting renders; test asserts every other status
  (DRAFT/PENDING/EXPIRED/DELETED/HIDDEN/BLOCKED) 404s at its detail URL.

- [ ] **T009** `templates/postings/browse.html` and `templates/postings/detail.html`,
  extending `base.html`.
  **Verify:** T007/T008's tests assert on rendered content (title, price) in addition to
  status codes.

---

## Phase E — Create, Submit, Confirm (plan.md §4, spec.md §4.2, §4.4)

- [ ] **T010** `create(request, site_slug)` — GET renders `PostingCreateForm`; POST calls
  `create_posting()` then `submit_posting()` on success and redirects to `submitted`; on
  `InvalidCategoryAssignment`/`InvalidPriceForPolicy`/`AreaRequired`, redisplays the form
  with `form.add_error(None, str(exc))` and the poster's other values preserved.
  **Verify:** test asserts a valid POST creates a PENDING posting and redirects; one test
  per exception type asserts the form redisplays with that error and no posting is left
  in an inconsistent state (either not created, or still correctly PENDING/DRAFT per which
  validation failed).

- [ ] **T011** `price_field_partial(request, site_slug)` — HTMX endpoint rendering
  `templates/postings/_price_field.html` for the selected category's `price_policy`.
  **Verify:** test asserts the response for a REQUIRED-policy category marks the field
  required; FORBIDDEN hides/disables it; OPTIONAL renders it as a normal optional field.

- [ ] **T012** `templates/postings/create.html` — the form, with the category `<select>`
  carrying `hx-get`/`hx-trigger="change"`/`hx-target` wired to T011's endpoint (plan.md §5).
  **Verify:** manual check in a browser — changing the category updates the price field
  without a full page reload.

- [ ] **T013** `submitted(request, site_slug, public_id, token)` — 404 via
  `get_posting_for_management` on a bad `public_id`/token; otherwise renders the
  confirm-link page.
  **Verify:** test asserts 200 with the confirm link present for a valid token; test
  asserts 404 for a wrong token and for a wrong `public_id`.

- [ ] **T014** `confirm(request, site_slug, public_id, token)` — calls `confirm_posting()`;
  on success redirects to `detail`; on `InvalidTransition`/`ConfirmationExpired`, renders
  `confirm_error.html` with the message.
  **Verify:** test asserts a PENDING-within-window posting becomes ACTIVE and redirects;
  test asserts a PENDING posting past `CONFIRMATION_WINDOW` renders the error page and
  stays PENDING; test asserts a non-PENDING posting (e.g. already ACTIVE) renders the
  error page via `InvalidTransition`.

- [ ] **T015** `templates/postings/submitted.html` and `templates/postings/confirm_error.html`.
  **Verify:** covered by T013/T014's tests asserting rendered content, not just status
  codes.

---

## Phase F — Manage Page (plan.md §4, spec.md §4.3, §4.4)

- [ ] **T016** `manage(request, site_slug, public_id, token)` — 404 via
  `get_posting_for_management`; renders current status, expiry, and the actions valid for
  that status (spec §4.3: renew+delete for ACTIVE/EXPIRED, neither for
  DELETED/HIDDEN/BLOCKED).
  **Verify:** one test per status asserting exactly the actions spec §4.3 says should be
  present/absent.

- [ ] **T017** `manage_delete(request, site_slug, public_id, token)` (`@require_POST`) —
  calls `delete_posting()`; on `InvalidTransition`, flashes the error via `messages.error`
  and redirects back to `manage` with no state change.
  **Verify:** test asserts an ACTIVE/EXPIRED/DRAFT/PENDING posting becomes DELETED; test
  asserts a BLOCKED and a HIDDEN posting reject with `InvalidTransition`, flash the
  message, and remain in their original status.

- [ ] **T018** `manage_renew(request, site_slug, public_id, token)` (`@require_POST`) —
  calls `renew_posting()`; on `InvalidTransition`/`RenewalTooSoon`/`RenewalWindowExpired`,
  flashes the error and redirects back with no state change.
  **Verify:** test asserts ACTIVE and EXPIRED postings renew successfully (EXPIRED case
  also asserts the reactivation to ACTIVE from `renew_posting`'s existing behavior); one
  test per rejection exception asserting the flash message and unchanged state.

- [ ] **T019** `templates/postings/manage.html` — status, expiry, renew/delete forms with
  `hx-confirm`/`hx-post` on delete per plan.md §5; renders `{% if messages %}` for flashed
  errors.
  **Verify:** manual check — deleting without confirming the `hx-confirm` dialog leaves
  the posting untouched; confirming deletes it.

---

## Phase G — Seed Data (plan.md §6)

- [ ] **T020** `apps/geo/management/commands/seed_dev_data.py` exactly as specified in
  plan.md §6 — `get_or_create` throughout, one dev Site, one Channel, two Categories
  (one OPTIONAL, one FORBIDDEN price policy, to exercise both branches of T011/T012
  manually).
  **Verify:** running it twice produces no duplicate rows; `uv run python manage.py seed_dev_data`
  then `Site.objects.count() == 1` in a shell check.

---

## Phase H — Acceptance Verification (spec.md §7)

- [ ] **T021** Run the full suite and report status:
  - `uv run python manage.py check`
  - `uv run pytest`
  - `uv run pytest --cov=apps --cov-report=term-missing` (≥ 80% on `apps/`)
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - Manual browser walkthrough (spec.md §7 acceptance criterion 4): `seed_dev_data`, run
    the dev server, create a posting at `/dev/post/`, confirm it via the link on the
    submitted page, see it on `/dev/browse/` and its detail page, then delete or renew it
    from its manage page.
  - Manual pass: confirm every spec.md §4 requirement is covered by at least one test
    name findable by `grep -r` in `tests/postings/`.
