# Plan 001: Domain Model & Posting Lifecycle

**Status:** Draft — awaiting review
**Implements:** `specs/001-domain-model/spec.md`

---

## 1. Amendments to the Spec's Entity List

Two places in `spec.md` state a requirement that the §3 field list cannot support. Both
are additive, minimal schema changes; neither touches §3 fields already listed, and both
were confirmed with the user before writing this plan.

1. **`Category.parent`** (nullable self-FK, `on_delete=PROTECT`, `related_name="children"`).
   §5.4 requires rejecting a posting assigned to a Category that "has child categories,"
   which is unenforceable without a self-referential field. A Category with no children is
   a leaf, matching the Domain Vocabulary's definition by construction.
2. **`Posting.submitted_at`** (nullable `DateTimeField`). §5.2 requires recording the
   submission time on the DRAFT → PENDING transition, and §5.3 gates confirmation to
   within 72 hours of it. `updated_at` is not a safe proxy — any unrelated save while
   PENDING would silently reset the confirmation window.

---

## 2. App Breakdown

Following the layout in `CLAUDE.md` §4:

| App | Models | Notes |
|---|---|---|
| `apps/geo` | `Site`, `Area` | Reference data, admin-managed |
| `apps/taxonomy` | `Channel`, `Category` | Reference data, admin-managed |
| `apps/postings` | `Posting`, `PostingImage` | Core lifecycle + `services.py` |
| `apps/moderation` | `Flag` | Flag model + `services.py`; review UI is out of scope |

`apps/search` is untouched — search is a separate, later feature. Each app gets a minimal
`admin.py` (`list_display`/`search_fields` only, no custom actions — see §6 on why
`BLOCKED` gets no admin entry point yet).

---

## 3. Schema

### `apps/geo/models.py`

```python
class Site(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    hostname = models.CharField(max_length=255, unique=True)
    timezone = models.CharField(max_length=64)  # IANA name, e.g. "America/Chicago"
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)


class Area(models.Model):
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="areas")
    slug = models.SlugField()
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("site", "slug")]
```

`is_active` on `Site`/`Area` is stored but not enforced against the postings queryset in
this feature — filtering browse/search by active geography belongs to the browse/search
feature, not the domain model.

### `apps/taxonomy/models.py`

```python
class Channel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)


class Category(models.Model):
    class PricePolicy(models.TextChoices):
        REQUIRED = "required", "Required"
        OPTIONAL = "optional", "Optional"
        FORBIDDEN = "forbidden", "Forbidden"

    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="categories")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    code = models.CharField(max_length=10)
    slug = models.SlugField()
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    lifetime_days = models.PositiveIntegerField()
    price_policy = models.CharField(max_length=10, choices=PricePolicy.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("channel", "code"), ("channel", "slug")]

    @property
    def is_leaf(self) -> bool:
        return not self.children.exists()
```

### `apps/postings/models.py`

```python
class Posting(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"
        HIDDEN = "hidden", "Hidden"
        BLOCKED = "blocked", "Blocked"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    site = models.ForeignKey("geo.Site", on_delete=models.PROTECT, related_name="postings")
    area = models.ForeignKey(
        "geo.Area",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="postings",
    )
    category = models.ForeignKey(
        "taxonomy.Category", on_delete=models.PROTECT, related_name="postings"
    )

    title = models.CharField(max_length=200)
    body = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    contact_email = models.EmailField()
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    show_phone = models.BooleanField(default=False)

    location_text = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    manage_token_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_renewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    reposted_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reposts",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["site", "category", "status", "published_at"], name="posting_visibility_idx"
            ),
            models.Index(fields=["status", "expires_at"], name="posting_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(price__isnull=True) | Q(price__gte=0),
                name="posting_price_nonnegative",
            ),
        ]


class PostingImage(models.Model):
    posting = models.ForeignKey(Posting, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="postings/%Y/%m/")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
```

`FK` choices: `PROTECT` on `site`/`area`/`category` because reference data is expected to
outlive postings and accidental cascade deletes would violate the "retain every posting
row permanently" rule. `reposted_from` uses `SET_NULL` — precautionary only, since posting
rows are never hard-deleted in normal operation.

The 24-image cap and the price/policy cross-field checks (`required`/`forbidden`) are
service-layer validation, not DB constraints — they depend on the related Category, which
a `CheckConstraint` can't reach.

### `apps/moderation/models.py`

```python
class Flag(models.Model):
    posting = models.ForeignKey("postings.Posting", on_delete=models.CASCADE, related_name="flags")
    reason = models.CharField(max_length=255)
    reporter_fingerprint = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("posting", "reporter_fingerprint")]
```

`reason` is free-text `CharField`, not `TextChoices` — the spec never enumerates flag
reasons, so inventing a fixed set here would be scope creep. `unique_together` enforces
the "same fingerprint counts once" rule at the DB level; the service layer uses
`get_or_create` rather than catching `IntegrityError`.

---

## 4. Manage Tokens & `public_id`

- `public_id`: `uuid.uuid4`, stored as `UUIDField(unique=True)`, distinct from the
  integer PK — satisfies "unique, non-sequential."
- Manage token: plaintext generated with `secrets.token_urlsafe(32)` (256 bits, well over
  the 128-bit floor), hashed for storage with `django.contrib.auth.hashers.make_password`
  (PBKDF2, salted — already a dependency via `django.contrib.auth`, no new package).
  Verified with `check_password(token, posting.manage_token_hash)`.
- A single lookup function, `get_posting_for_management(public_id, token)`, raises
  `Posting.DoesNotExist` both when the `public_id` doesn't resolve and when the token
  doesn't match — one code path, so callers 404 uniformly per CLAUDE.md §8.

---

## 5. State Machine (`apps/postings/services.py`)

Fixed business constants (not settings — the spec states these as literal numbers, unlike
the flag threshold which §9.2 explicitly calls "configured"):

```python
CONFIRMATION_WINDOW = timedelta(hours=72)
RENEWAL_MIN_INTERVAL = timedelta(hours=48)
RENEWAL_GRACE_PERIOD = timedelta(days=7)
MAX_POSTING_IMAGES = 24
```

Transitions, each a service function raising a specific exception from
`apps/postings/exceptions.py` on rejection:

| Function | Transition | Rejects with |
|---|---|---|
| `create_posting(...)` | — → `DRAFT` | `InvalidCategoryAssignment`, `InvalidPriceForPolicy`, `AreaRequired` |
| `submit_posting(posting)` | `DRAFT` → `PENDING` | `InvalidTransition` |
| `confirm_posting(posting)` | `PENDING` → `ACTIVE` | `InvalidTransition`, `ConfirmationExpired` |
| `renew_posting(posting)` | `ACTIVE`/`EXPIRED` → `ACTIVE` | `InvalidTransition`, `RenewalTooSoon`, `RenewalWindowExpired` |
| `delete_posting(posting)` | `DRAFT`/`PENDING`/`ACTIVE`/`EXPIRED` → `DELETED` | `InvalidTransition` |
| `expire_active_postings()` | bulk `ACTIVE` → `EXPIRED` where `expires_at` passed | — (bulk `update`, no per-row exceptions) |
| `hide_posting(posting)` | `ACTIVE` → `HIDDEN` | `InvalidTransition` |
| `block_posting(posting)` | any non-`DELETED` → `BLOCKED` | `InvalidTransition` |
| `repost_posting(source, token)` | reads `source`, creates new `Posting` with `reposted_from=source` | `InvalidManageToken` (via `Posting.DoesNotExist`), `InvalidTransition` if `source.status == BLOCKED` |
| `add_posting_image(posting, image)` | — | `ImageLimitExceeded` |

Two explicit design calls, flagged for review before implementation:

- **Renewing an `EXPIRED` posting sets `status` back to `ACTIVE`.** The spec's event
  description only says renewal updates `expires_at`/`last_renewed_at`, but leaving an
  `EXPIRED` posting `EXPIRED` with a future expiry date would make it permanently
  unreachable through the visible queryset — renewal only makes sense if it revives the
  posting.
- **`block_posting()` has no call site in this feature.** It exists so the state machine
  and its rejection tests are complete, but nothing in `spec.md` defines the operator
  event that triggers `BLOCKED` — no admin action or view is wired up. That entry point
  is deferred to the moderation feature (`apps/moderation`'s review interface is
  explicitly out of scope for spec 001).

`apps/moderation/services.py` owns `flag_posting(posting, reason, reporter_fingerprint)`:
`get_or_create`s a `Flag`, counts distinct flags on the posting, and calls
`postings.services.hide_posting(posting)` if the count reaches
`settings.FLAG_HIDE_THRESHOLD` and the posting is still `ACTIVE`.

---

## 6. Settings

Add to `config/settings.py`, documented in `.env.example`:

```python
FLAG_HIDE_THRESHOLD = int(os.environ.get("FLAG_HIDE_THRESHOLD", "5"))
```

Add `"apps.geo"`, `"apps.taxonomy"`, `"apps.postings"`, `"apps.moderation"` to
`INSTALLED_APPS`. Each app gets an `apps.py` with `AppConfig.name = "apps.<name>"`
matching the nested package path.

### Runtime Dependency: `pillow`

Recorded per CLAUDE.md §2, which requires a rationale in the relevant `plan.md` for every
runtime dependency.

`PostingImage.image` is a `models.ImageField` (§3). Django's `ImageField` hard-requires
Pillow — `makemigrations` raises a system check error (`fields.E210`) without it — so this
is not a library chosen over a standard-library alternative but a prerequisite of the
framework feature being used. The alternative, storing a path in a `CharField` and
validating dimensions by hand, would mean writing image-format code the framework already
provides, against CLAUDE.md §1's "boring is correct."

Note that image *upload handling, storage backends, and resizing* remain out of scope for
this feature (spec §7); only the field and its model are in scope here.

---

## 7. Visible Queryset & Query Budget

`apps/postings/models.py` gets a custom manager:

```python
class PostingQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(status=Posting.Status.ACTIVE)


class Posting(models.Model):
    objects = PostingQuerySet.as_manager()
    ...
```

This is the single canonical queryset required by §5.1 — every later browse/search
feature filters through `Posting.objects.visible()`, never re-deriving the status
condition. Callers are expected to chain
`.select_related("category", "area").prefetch_related("images")` to stay within the
3-query budget (1 for the page of postings, 1 for image prefetch, 1 for `.count()` if
paginating) — this plan defines the queryset; the page-rendering view that chains it is
out of scope here.

---

## 8. Migrations

Order: `geo` → `taxonomy` → `postings` → `moderation` (matches FK dependency order).
Run `uv run python manage.py makemigrations geo taxonomy postings moderation` once models
are written, then `uv run python manage.py migrate` against a fresh database as part of
verification.

---

## 9. Testing

- `tests/factories.py`: `make_site()`, `make_area()`, `make_channel()`, `make_category()`,
  `make_posting(status=Posting.Status.ACTIVE, **overrides)`. The posting factory sets
  fields directly for the requested status (rather than replaying every transition) so
  each transition function can be tested in isolation from a known starting state.
- Layout mirrors `apps/`: `tests/geo/`, `tests/taxonomy/`, `tests/postings/`,
  `tests/moderation/`, each with `test_models.py` and (where relevant) `test_services.py`.
- Every accepted transition in §5 gets a test; every rejection path
  (`InvalidTransition`, `RenewalTooSoon`, `RenewalWindowExpired`, `ConfirmationExpired`,
  `InvalidCategoryAssignment`, `ImageLimitExceeded`, negative price, duplicate flag
  fingerprint, non-leaf category assignment) gets its own test per CLAUDE.md §6.
- All tests use `pytest.mark.django_db`, no `TestCase` classes, per CLAUDE.md §6.

---

## 10. Verification

1. `uv run python manage.py makemigrations --check` — models match migrations.
2. `uv run python manage.py migrate` against an empty database — applies cleanly.
3. `uv run pytest` — full suite passes.
4. `uv run pytest --cov=apps --cov-report=term-missing` — ≥ 80% line coverage on `apps/`.
5. `uv run ruff check .` and `uv run ruff format --check .` — clean.
6. Manual spot check: every §5 requirement in `spec.md` maps to at least one test name
   findable by `grep -r` in `tests/`.
