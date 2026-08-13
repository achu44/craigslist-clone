from datetime import timedelta

import pytest
from django.utils import timezone

from apps.postings.models import Posting
from apps.search.services import MAX_QUERY_LENGTH, normalize_query, search_postings
from tests.factories import make_area, make_category, make_posting, make_site


def _visible(site):
    return Posting.objects.visible().filter(site=site)


# --- normalize_query (T003) ------------------------------------------------


def test_normalize_query_returns_empty_for_none():
    assert normalize_query(None) == ""


def test_normalize_query_returns_empty_for_empty_string():
    assert normalize_query("") == ""


def test_normalize_query_returns_empty_for_whitespace_only():
    assert normalize_query("   \t\n ") == ""


def test_normalize_query_strips_surrounding_whitespace():
    assert normalize_query("  couch  ") == "couch"


def test_normalize_query_truncates_over_long_input():
    assert normalize_query("a" * 500) == "a" * MAX_QUERY_LENGTH


# --- search_postings matching (T004) ---------------------------------------


@pytest.mark.django_db
def test_search_matches_term_in_title():
    site = make_site()
    make_posting(site=site, title="Blue velvet couch", body="Nothing else here")

    results = search_postings(_visible(site), "couch")

    assert [p.title for p in results] == ["Blue velvet couch"]


@pytest.mark.django_db
def test_search_matches_term_in_body():
    site = make_site()
    make_posting(site=site, title="Furniture", body="A blue velvet couch, barely used")

    results = search_postings(_visible(site), "couch")

    assert [p.title for p in results] == ["Furniture"]


@pytest.mark.django_db
def test_search_returns_nothing_when_term_matches_neither_field():
    site = make_site()
    make_posting(site=site, title="Blue velvet couch", body="Barely used")

    assert list(search_postings(_visible(site), "bicycle")) == []


@pytest.mark.django_db
def test_search_ignores_fields_outside_title_and_body():
    """Spec 003 §4.1: contact fields, location_text, Category and Area names are not
    searched, even though they sit on (or join to) the same row."""
    site = make_site()
    area = make_area(site=site, name="Riverbend")
    category = make_category(name="Riverbend")
    make_posting(
        site=site,
        area=area,
        category=category,
        title="Oak desk",
        body="Solid wood",
        contact_name="Riverbend",
        contact_email="riverbend@example.com",
        location_text="Riverbend",
    )

    assert list(search_postings(_visible(site), "riverbend")) == []


# --- empty term is a no-op (T005) ------------------------------------------


@pytest.mark.django_db
def test_search_returns_input_queryset_unchanged_for_empty_term():
    site = make_site()
    queryset = _visible(site)

    assert search_postings(queryset, "") is queryset


@pytest.mark.django_db
def test_search_with_empty_term_preserves_browse_ordering():
    site = make_site()
    now = timezone.now()
    make_posting(site=site, title="Older", published_at=now - timedelta(days=2))
    make_posting(site=site, title="Newer", published_at=now - timedelta(days=1))

    queryset = _visible(site).order_by("-published_at")

    assert [p.title for p in search_postings(queryset, "")] == ["Newer", "Older"]


# --- ranking (T006) ---------------------------------------------------------


@pytest.mark.django_db
def test_title_match_outranks_body_only_match():
    site = make_site()
    now = timezone.now()
    # The body-only match is the *newer* posting, so if ranking were ignored and the
    # -published_at tie-break drove the order, this assertion would fail.
    make_posting(site=site, title="Couch", body="Sturdy", published_at=now - timedelta(days=2))
    make_posting(site=site, title="Furniture", body="A couch", published_at=now - timedelta(days=1))

    results = search_postings(_visible(site), "couch")

    assert [p.title for p in results] == ["Couch", "Furniture"]


@pytest.mark.django_db
def test_equally_ranked_results_are_ordered_newest_first():
    site = make_site()
    now = timezone.now()
    make_posting(site=site, title="Couch", body="Same text", published_at=now - timedelta(days=2))
    make_posting(site=site, title="Couch", body="Same text", published_at=now - timedelta(days=1))

    for _ in range(3):
        results = list(search_postings(_visible(site), "couch"))
        published = [p.published_at for p in results]
        assert published == sorted(published, reverse=True)


# --- visibility (T007) ------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        Posting.Status.DRAFT,
        Posting.Status.PENDING,
        Posting.Status.EXPIRED,
        Posting.Status.DELETED,
        Posting.Status.HIDDEN,
        Posting.Status.BLOCKED,
    ],
)
def test_search_never_returns_a_non_visible_posting(status):
    site = make_site()
    make_posting(site=site, status=status, title="couch", body="couch")

    assert list(search_postings(_visible(site), "couch")) == []


# --- site boundary (T008) ---------------------------------------------------


@pytest.mark.django_db
def test_search_does_not_cross_site_boundary():
    site = make_site()
    other_site = make_site()
    make_posting(site=site, title="Couch on this site")
    make_posting(site=other_site, title="Couch on another site")

    results = search_postings(_visible(site), "couch")

    assert [p.title for p in results] == ["Couch on this site"]


# --- hostile input (T009) ---------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "term",
    [
        "desk & chair | !sofa",
        "(unbalanced",
        "couch:*",
        "!!! & | ()",
    ],
)
def test_full_text_operators_are_treated_as_literal_text(term):
    site = make_site()
    make_posting(site=site, title="Blue velvet couch", body="Barely used")

    # Evaluating the queryset is what would raise if the term reached tsquery as syntax.
    assert isinstance(list(search_postings(_visible(site), term)), list)


@pytest.mark.django_db
def test_operator_soup_still_matches_its_literal_words():
    site = make_site()
    make_posting(site=site, title="Oak desk", body="With a matching chair")
    make_posting(site=site, title="Blue velvet couch", body="Barely used")

    results = search_postings(_visible(site), "desk & chair")

    assert [p.title for p in results] == ["Oak desk"]
