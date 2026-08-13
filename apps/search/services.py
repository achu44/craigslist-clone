from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import QuerySet

MAX_QUERY_LENGTH = 200
SEARCH_CONFIG = "english"


def normalize_query(raw: str | None) -> str:
    """Whitespace-only input is not a search (spec 003 §4.4); over-long input is trimmed
    rather than rejected."""
    if not raw:
        return ""
    return raw.strip()[:MAX_QUERY_LENGTH]


def search_postings(postings: QuerySet, term: str) -> QuerySet:
    if not term:
        return postings
    # Weighted so a title match outranks a body-only one. A single unweighted
    # SearchVector("title", "body") puts both fields at PostgreSQL's default weight D,
    # which scores the two identically and leaves relevance unable to tell them apart.
    vector = SearchVector("title", weight="A", config=SEARCH_CONFIG) + SearchVector(
        "body", weight="B", config=SEARCH_CONFIG
    )
    query = SearchQuery(term, config=SEARCH_CONFIG, search_type="plain")
    return (
        postings.annotate(search=vector, rank=SearchRank(vector, query))
        .filter(search=query)
        # SearchRank alone leaves ties in database order, which is not stable between
        # requests; -published_at makes the ordering deterministic (spec 003 §4.2).
        .order_by("-rank", "-published_at")
    )
