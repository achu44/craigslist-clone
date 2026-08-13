from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.geo.models import Site
from apps.search.services import normalize_query, search_postings
from apps.taxonomy.models import Category

from .exceptions import (
    AreaRequired,
    ConfirmationExpired,
    InvalidCategoryAssignment,
    InvalidPriceForPolicy,
    InvalidTransition,
    RenewalTooSoon,
    RenewalWindowExpired,
)
from .forms import PostingCreateForm
from .models import Posting
from .services import (
    confirm_posting,
    create_posting,
    delete_posting,
    get_posting_for_management,
    renew_posting,
    submit_posting,
)


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
    term = normalize_query(request.GET.get("q"))
    postings = search_postings(postings, term)
    categories = Category.objects.filter(is_active=True)
    return render(
        request,
        "postings/browse.html",
        {
            "site": site,
            "postings": postings,
            "categories": categories,
            "selected_category": category_slug,
            "term": term,
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
    category = get_object_or_404(Category, pk=request.GET.get("category"), is_active=True)
    return render(request, "postings/_price_field.html", {"category": category})


def submitted(request, site_slug, public_id, token):
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    posting = _get_posting_or_404(public_id, token)
    return render(
        request,
        "postings/submitted.html",
        {"site": site, "posting": posting, "token": token},
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
    can_renew = posting.status in (Posting.Status.ACTIVE, Posting.Status.EXPIRED)
    can_delete = posting.status in (
        Posting.Status.DRAFT,
        Posting.Status.PENDING,
        Posting.Status.ACTIVE,
        Posting.Status.EXPIRED,
    )
    return render(
        request,
        "postings/manage.html",
        {
            "site": site,
            "posting": posting,
            "token": token,
            "can_renew": can_renew,
            "can_delete": can_delete,
        },
    )


@require_POST
def manage_delete(request, site_slug, public_id, token):
    posting = _get_posting_or_404(public_id, token)
    try:
        delete_posting(posting)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    return redirect("postings:manage", site_slug=site_slug, public_id=public_id, token=token)


@require_POST
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
        raise Http404 from None
