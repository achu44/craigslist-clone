# Tasks 001: Domain Model & Posting Lifecycle

**Implements:** `specs/001-domain-model/spec.md` per `specs/001-domain-model/plan.md`

Tasks are ordered by dependency. Each is atomic and independently verifiable; run the
listed verification before moving to the next task. Cite this file
(`refs specs/001-domain-model/tasks.md`) in commit bodies alongside the spec per
CLAUDE.md §9.

---

## Phase A — App Scaffolding

- [ ] **T001** Create `apps/__init__.py` and the four app packages (`apps/geo`,
  `apps/taxonomy`, `apps/postings`, `apps/moderation`), each with `__init__.py` and an
  `apps.py` (`AppConfig.name = "apps.<name>"`).
  **Verify:** `uv run python manage.py check` runs without `ModuleNotFoundError`.

- [ ] **T002** Register all four apps in `config/settings.py` `INSTALLED_APPS`.
  **Verify:** `uv run python manage.py check` passes with no missing-app errors.

---

## Phase B — Models (plan.md §3)

- [ ] **T003** `apps/geo/models.py`: `Site` and `Area` models exactly as specified in
  plan.md §3, including `unique_together` on `Area`.
  **Verify:** `uv run python manage.py makemigrations geo` produces a migration with no
  warnings.

- [ ] **T004** `apps/taxonomy/models.py`: `Channel` and `Category` models, including the
  `Category.parent` self-FK (plan.md §1 amendment) and `PricePolicy` TextChoices.
  **Verify:** `uv run python manage.py makemigrations taxonomy` produces a migration with
  no warnings.

- [ ] **T005** `apps/postings/models.py`: `Posting` model, including `submitted_at`
  (plan.md §1 amendment), the `Status` TextChoices, both indexes, and the
  `posting_price_nonnegative` `CheckConstraint`.
  **Verify:** `uv run python manage.py makemigrations postings` produces a migration
  containing both named indexes and the constraint.

- [ ] **T006** `apps/postings/models.py`: `PostingImage` model.
  **Verify:** Migration from T005/T006 applies; `PostingImage.objects.all()` is queryable
  in `manage.py shell`.

- [ ] **T007** `apps/moderation/models.py`: `Flag` model, including `unique_together` on
  `(posting, reporter_fingerprint)`.
  **Verify:** `uv run python manage.py makemigrations moderation` produces a migration
  with no warnings.

- [ ] **T008** Apply all migrations to a fresh local database.
  **Verify:** `uv run python manage.py migrate` succeeds against an empty database
  (spec.md §8 acceptance criterion 4).

---

## Phase C — Admin (minimal, read/search only)

- [ ] **T009** `admin.py` in each of the four apps: register every model with
  `list_display`/`search_fields` only. No custom actions (plan.md §2, §5 — `block_posting`
  gets no admin entry point in this feature).
  **Verify:** `uv run python manage.py check` passes; each model is visible and searchable
  at `/admin/` in a manual spot check.

---

## Phase D — Settings

- [ ] **T010** Add `FLAG_HIDE_THRESHOLD` to `config/settings.py` (env-backed, default
  `5`) and document it in `.env.example` (plan.md §6).
  **Verify:** `uv run python manage.py shell -c "from django.conf import settings; print(settings.FLAG_HIDE_THRESHOLD)"` prints `5` with no env override set.

---

## Phase E — Exceptions and Token Helpers

- [ ] **T011** `apps/postings/exceptions.py`: `InvalidTransition`, `RenewalTooSoon`,
  `RenewalWindowExpired`, `ConfirmationExpired`, `InvalidCategoryAssignment`,
  `InvalidPriceForPolicy`, `AreaRequired`, `ImageLimitExceeded` — all subclassing a
  common `PostingError`.
  **Verify:** `uv run ruff check apps/postings/exceptions.py` passes; module imports
  cleanly.

- [ ] **T012** `apps/postings/services.py`: manage-token helpers —
  `generate_manage_token()` (returns `(plaintext, hash)` via `secrets.token_urlsafe(32)`
  + `make_password`) and `get_posting_for_management(public_id, token)` (raises
  `Posting.DoesNotExist` on either a bad `public_id` or a bad token — plan.md §4).
  **Verify:** unit test in `tests/postings/test_services.py` — a valid token resolves the
  posting; a wrong token and a wrong `public_id` both raise `Posting.DoesNotExist`.

---

## Phase F — Custom QuerySet

- [ ] **T013** `apps/postings/models.py`: `PostingQuerySet.visible()` and wire it as
  `Posting.objects` (plan.md §7 — the single canonical visible queryset, spec.md §5.1).
  **Verify:** test asserts `Posting.objects.visible()` returns only `ACTIVE` postings
  across all seven statuses.

---

## Phase G — Lifecycle Services (plan.md §5)

Each of the following is one function in `apps/postings/services.py` plus its rejection
paths. Implement and test each before moving to the next — do not batch multiple
transitions into one commit.

- [ ] **T014** `create_posting(...)` → `DRAFT`. Validates: category is a leaf
  (`InvalidCategoryAssignment`), price matches `price_policy`
  (`InvalidPriceForPolicy`), area required if the site has any areas (`AreaRequired`).
  Generates and returns `(posting, plaintext_token)`.

- [ ] **T015** `submit_posting(posting)`: `DRAFT` → `PENDING`, sets `submitted_at`.
  Rejects from any other status (`InvalidTransition`).

- [ ] **T016** `confirm_posting(posting)`: `PENDING` → `ACTIVE` within
  `CONFIRMATION_WINDOW` (72h) of `submitted_at`; sets `published_at` and computes
  `expires_at` from `category.lifetime_days`. Rejects outside the window
  (`ConfirmationExpired`) or from any other status (`InvalidTransition`).

- [ ] **T017** `renew_posting(posting)`: `ACTIVE`/`EXPIRED` → `ACTIVE` (confirmed
  behavior: reviving an `EXPIRED` posting — plan.md §5). Enforces
  `RENEWAL_MIN_INTERVAL` (48h since `published_at`/`last_renewed_at`, whichever is
  later — `RenewalTooSoon`) and `RENEWAL_GRACE_PERIOD` (7 days past `expires_at` —
  `RenewalWindowExpired`). Rejects from any other status (`InvalidTransition`).

- [ ] **T018** `delete_posting(posting)`: `DRAFT`/`PENDING`/`ACTIVE`/`EXPIRED` →
  `DELETED`, sets `removed_at`. Rejects from `BLOCKED` and `HIDDEN`
  (`InvalidTransition`).

- [ ] **T019** `expire_active_postings()`: bulk `ACTIVE` → `EXPIRED` where `expires_at`
  has passed. Bulk `update()`, no per-row exceptions.

- [ ] **T020** `hide_posting(posting)`: `ACTIVE` → `HIDDEN`, sets `removed_at`. Rejects
  from any other status (`InvalidTransition`).

- [ ] **T021** `block_posting(posting)`: any status except `DELETED` → `BLOCKED`, sets
  `removed_at`. Rejects from `DELETED` (`InvalidTransition`). No caller wired yet
  (confirmed — plan.md §5).

- [ ] **T022** `repost_posting(source, token)`: validates `token` against `source`
  (`Posting.DoesNotExist` on mismatch), rejects if `source.status == BLOCKED`
  (`InvalidTransition`), creates a new `DRAFT` posting copying postable fields, with a
  fresh `public_id`/manage token and `reposted_from=source`.

- [ ] **T023** `add_posting_image(posting, image)`: rejects the 25th image
  (`ImageLimitExceeded`, `MAX_POSTING_IMAGES = 24`).

**Verify (whole phase):** every transition in the plan.md §5 table has a passing test for
its accepted path, and one test per listed exception for its rejected path.

---

## Phase H — Moderation Service

- [ ] **T024** `apps/moderation/services.py`: `flag_posting(posting, reason,
  reporter_fingerprint)` — `get_or_create`s a `Flag`, counts distinct flags, calls
  `postings.services.hide_posting(posting)` when the count reaches
  `settings.FLAG_HIDE_THRESHOLD` and the posting is `ACTIVE`.
  **Verify:** test asserts repeat flags from the same fingerprint count once (no
  duplicate row, no premature hide); test asserts crossing the threshold with distinct
  fingerprints transitions the posting to `HIDDEN`.

---

## Phase I — Expiry Management Command

- [ ] **T025** `apps/postings/management/commands/expire_postings.py`: thin wrapper
  calling `expire_active_postings()` (CLAUDE.md §2 — cron-invoked management command,
  no Celery).
  **Verify:** `uv run python manage.py expire_postings` runs against a fixture with a
  past-due `ACTIVE` posting and leaves it `EXPIRED`.

---

## Phase J — Factories and Cross-Cutting Tests

- [ ] **T026** `tests/factories.py`: `make_site`, `make_area`, `make_channel`,
  `make_category`, `make_posting(status=..., **overrides)` — the posting factory sets
  fields directly for the requested status rather than replaying transitions (plan.md
  §9).
  **Verify:** a factory call for each of the seven `Status` values produces a model that
  passes `full_clean()`.

- [ ] **T027** `tests/postings/test_models.py`: negative price is rejected at the DB
  constraint level; the visibility and expiry indexes exist (introspect via
  `Posting._meta.indexes`, not a live query-plan assertion, per CLAUDE.md §6 on not
  testing ORM internals).

- [ ] **T028** `tests/taxonomy/test_models.py`: assigning a posting to a non-leaf
  Category is rejected (covers the `Category.parent` amendment end-to-end via
  `create_posting`).

---

## Phase K — Acceptance Verification (spec.md §8)

- [ ] **T029** Run the full suite and report status:
  - `uv run pytest`
  - `uv run pytest --cov=apps --cov-report=term-missing` (≥ 80% on `apps/`)
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run python manage.py makemigrations --check` (no drift)
  - Manual pass: confirm every spec.md §5 requirement is covered by at least one test
    name in `tests/`.
