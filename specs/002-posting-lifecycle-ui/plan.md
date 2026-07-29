# Plan 002: Posting Lifecycle UI

**Status:** Draft — awaiting review
**Implements:** `specs/002-posting-lifecycle-ui/spec.md`

No new models or migrations. Everything here is views, URLs, forms, templates, static
assets, settings wiring, and one management command, built on the existing
`apps/postings/services.py` functions (unchanged, shown in full below for reference).

---

## 1. Settings & Project Wiring

`config/settings.py`:

```python
INSTALLED_APPS = [
    ...,
    'django_htmx',
    'apps.geo',
    'apps.taxonomy',
    'apps.postings',
    'apps.moderation',
]

MIDDLEWARE = [
    ...,
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        ...,
        'DIRS': [BASE_DIR / 'templates'],
        ...
    },
]

STATICFILES_DIRS = [BASE_DIR / 'static']
```

`django.contrib.messages` is already installed (it's in the default `startproject`
scaffold) but wasn't yet used — this feature is the first to rely on it, for flashing
delete/renew rejection errors on the manage page (§4.4).

`config/urls.py`:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.postings.urls")),
]
```

---

## 2. URL Structure (`apps/postings/urls.py`, `app_name = 'postings'`)

Site is resolved from the path everywhere, per spec §4.1 / §8.2:

```python
urlpatterns = [
    path("<slug:site_slug>/browse/", views.browse, name="browse"),
    path("<slug:site_slug>/post/", views.create, name="create"),
    path("<slug:site_slug>/post/price-field/", views.price_field_partial, name="price_field"),
    path("<slug:site_slug>/postings/<uuid:public_id>/", views.detail, name="detail"),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/submitted/<str:token>/",
        views.submitted,
        name="submitted",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/confirm/<str:token>/",
        views.confirm,
        name="confirm",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/",
        views.manage,
        name="manage",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/delete/",
        views.manage_delete,
        name="manage_delete",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/renew/",
        views.manage_renew,
        name="manage_renew",
    ),
]
```

`token` uses `<str:token>` rather than `<slug:token>` — `secrets.token_urlsafe()`'s
alphabet happens to satisfy the slug pattern today, but the URL shouldn't silently break
if that ever changes. `confirm` is a `GET` (matches how a real emailed link would work;
it's already gated behind possession of the unguessable token, same trust model as email).
`manage_delete`/`manage_renew` are `POST`-only.

---

## 3. Forms (`apps/postings/forms.py`)

One plain `forms.Form` (not a `ModelForm`) — field-level cleaning only. All domain rules
(leaf category, price policy, area requirement) stay in `create_posting()`, per CLAUDE.md
§7's "business logic ... out of ... views; domain rules belong in ... services.py."

```python
class PostingCreateForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.none())
    area = forms.ModelChoiceField(queryset=Area.objects.none(), required=False)
    title = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea)
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    contact_email = forms.EmailField()
    contact_name = forms.CharField(max_length=100, required=False)
    contact_phone = forms.CharField(max_length=32, required=False)
    show_phone = forms.BooleanField(required=False)
    location_text = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, site, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = (
            Category.objects.filter(is_active=True)
            .annotate(child_count=models.Count("children"))
            .filter(child_count=0)
        )
        if site.areas.exists():
            self.fields["area"].queryset = site.areas.all()
            self.fields["area"].required = True
        else:
            del self.fields["area"]
```

The category queryset is pre-filtered to leaves only — a UX nicety so a poster can't even
select a category that `create_posting()` would reject, though that rejection path is
still tested (§4.4) since the form-level filter is a convenience, not the enforcement.

---

## 4. Views (`apps/postings/views.py`)

Each view is a thin wrapper: resolve `site` (and `posting` via
`get_posting_for_management` where a token is involved), call the relevant service
function, translate its exceptions into either form errors or a `messages` flash, render
or redirect.

```python
def browse(request, site_slug):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    postings = (
        Posting.objects.visible()
        .filter(site=site)
        .select_related("category", "area")
        .order_by("-published_at")
    )
    category_slug = request.GET.get("category")
    if category_slug:
        postings = postings.filter(category__slug=category_slug)
    categories = Category.objects.filter(is_active=True)
    return render(
        request,
        "postings/browse.html",
        {
            "site": site,
            "postings": postings,
            "categories": categories,
            "selected_category": category_slug,
        },
    )


def detail(request, site_slug, public_id):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    posting = get_object_or_404(Posting.objects.visible().filter(site=site), public_id=public_id)
    return render(request, "postings/detail.html", {"site": site, "posting": posting})


def create(request, site_slug):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    if request.method == "POST":
        form = PostingCreateForm(request.POST, site=site)
        if form.is_valid():
            try:
                posting, token = create_posting(site=site, **form.cleaned_data)
            except (InvalidCategoryAssignment, InvalidPriceForPolicy, AreaRequired) as exc:
                form.add_error(None, str(exc))
            else:
                submit_posting(posting)
                return redirect(
                    "postings:submitted",
                    site_slug=site.slug,
                    public_id=posting.public_id,
                    token=token,
                )
    else:
        form = PostingCreateForm(site=site)
    return render(request, "postings/create.html", {"site": site, "form": form})


def price_field_partial(request, site_slug):
    """HTMX endpoint: re-renders just the price field's required/hidden state when the
    category select changes — the one place a static form can't express spec §4.5."""
    category = get_object_or_404(Category, pk=request.GET.get("category"), is_active=True)
    return render(request, "postings/_price_field.html", {"category": category})


def submitted(request, site_slug, public_id, token):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    posting = _get_posting_or_404(public_id, token)
    return render(
        request, "postings/submitted.html", {"site": site, "posting": posting, "token": token}
    )


def confirm(request, site_slug, public_id, token):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    posting = _get_posting_or_404(public_id, token)
    try:
        confirm_posting(posting)
    except (InvalidTransition, ConfirmationExpired) as exc:
        return render(request, "postings/confirm_error.html", {"site": site, "error": str(exc)})
    return redirect("postings:detail", site_slug=site.slug, public_id=posting.public_id)


def manage(request, site_slug, public_id, token):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    posting = _get_posting_or_404(public_id, token)
    return render(
        request, "postings/manage.html", {"site": site, "posting": posting, "token": token}
    )


def manage_delete(request, site_slug, public_id, token):
    posting = _get_posting_or_404(public_id, token)
    try:
        delete_posting(posting)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    return redirect("postings:manage", site_slug=site_slug, public_id=public_id, token=token)


def manage_renew(request, site_slug, public_id, token):
    posting = _get_posting_or_404(public_id, token)
    try:
        renew_posting(posting)
    except (InvalidTransition, RenewalTooSoon, RenewalWindowExpired) as exc:
        messages.error(request, str(exc))
    return redirect("postings:manage", site_slug=site_slug, public_id=public_id, token=token)


def _get_posting_or_404(public_id, token):
    try:
        return get_posting_for_management(public_id, token)
    except Posting.DoesNotExist:
        raise Http404
```

`manage_delete`/`manage_renew` only require the `POST` decorator (`@require_POST`) —
there's no separate confirmation view; the confirmation happens client-side (§5 below).

---

## 5. Templates & HTMX Usage

`templates/base.html` — single shared layout: `<head>` loads `static/css/base.css` and
htmx from `django_htmx/htmx-2.min.js`, plus a `{% block content %}`.

No CDN, and no vendored copy of htmx in this repository: `django-htmx` (already a
dependency for `HtmxMiddleware`) ships the htmx bundle as a static file at
`django_htmx/static/django_htmx/htmx-2.min.js`, so `{% static %}` resolves it from the
installed package. This is CLAUDE.md's dependency policy applied as written — use what a
dependency already provides rather than adding a second copy of it — and it keeps htmx
upgrades tied to `uv sync` instead of a manual re-download.

Per-page templates under `templates/postings/`: `browse.html`, `detail.html`,
`create.html`, `submitted.html`, `confirm_error.html`, `manage.html`, and one partial,
`_price_field.html`.

Two narrow, justified HTMX touches (matches spec §4.1's "isolated enhancements" rule —
everything else is a plain server-rendered form/link):

1. **Delete confirmation.** The delete button in `manage.html` is a real
   `<form method="post" hx-post="..." hx-confirm="Delete this posting? This cannot be undone.">`.
   Without JS it's an ordinary POST with no dialog (spec §5's progressive-enhancement
   requirement); with htmx, the confirm dialog gates the request.
2. **Dynamic price field.** The category `<select>` in `create.html` carries
   `hx-get="{% url 'postings:price_field' site.slug %}" hx-trigger="change" hx-target="#price-field-wrapper"`,
   swapping in `_price_field.html` rendered server-side from the selected category's
   `price_policy` — the one requirement (§4.5) that genuinely can't be expressed by a
   static form.

No other fragment-swapping; every other link/form is a normal full-page request.

---

## 6. Seed Data (`apps/geo/management/commands/seed_dev_data.py`)

```python
class Command(BaseCommand):
    help = "Create a small set of dev-only Site/Channel/Category rows for local use."

    def handle(self, *args, **options):
        site, _ = Site.objects.get_or_create(
            slug="dev",
            defaults={
                "name": "Dev Site",
                "hostname": "dev.localhost",
                "timezone": "UTC",
                "latitude": 0,
                "longitude": 0,
            },
        )
        channel, _ = Channel.objects.get_or_create(slug="for-sale", defaults={"name": "For Sale"})
        Category.objects.get_or_create(
            channel=channel,
            code="gen",
            defaults={
                "slug": "general",
                "name": "General",
                "lifetime_days": 30,
                "price_policy": Category.PricePolicy.OPTIONAL,
            },
        )
        Category.objects.get_or_create(
            channel=channel,
            code="fre",
            defaults={
                "slug": "free",
                "name": "Free Stuff",
                "lifetime_days": 7,
                "price_policy": Category.PricePolicy.FORBIDDEN,
            },
        )
        self.stdout.write(self.style.SUCCESS(f'Seeded site "{site.slug}".'))
```

`get_or_create` throughout so the command is safe to re-run. Lives under `apps/geo` since
`Site` is the root of what it creates; it reaches into `apps/taxonomy` the same way a
view or service function would (no circular dependency — `taxonomy` doesn't import `geo`).

---

## 7. Testing

New test modules under `tests/postings/`: `test_views_browse.py`, `test_views_create.py`,
`test_views_confirm.py`, `test_views_manage.py` — using Django's/pytest-django's test
`client` fixture, `pytest.mark.django_db`, and the existing `tests/factories.py` helpers
(`make_site`, `make_area`, `make_category`, `make_posting`) plus `reverse()` for URLs.
Every accepted path and every rejection path from spec §4.2/§4.4 gets its own test, same
convention as spec 001. `tests/geo/test_management_commands.py` covers `seed_dev_data`
(idempotency via a second run, and that it produces at least one leaf category).

---

## 8. Verification

1. `uv run python manage.py check` — settings/URL wiring is valid.
2. `uv run pytest` — full suite passes; coverage on `apps/` stays ≥ 80%.
3. `uv run ruff check .` / `uv run ruff format --check .` — clean.
4. Manual walkthrough in a real browser (spec §7 acceptance criterion 4):
   `uv run python manage.py seed_dev_data`, then `uv run python manage.py runserver`,
   create a posting at `/dev/post/`, confirm it via the link on the submitted page, see it
   at `/dev/browse/` and its detail page, then delete or renew it from its manage page.
