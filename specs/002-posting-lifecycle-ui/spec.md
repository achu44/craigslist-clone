# Spec 002: Posting Lifecycle UI

**Status:** Draft — awaiting review
**Depends on:** `specs/001-domain-model/spec.md` (Site, Area, Channel, Category, Posting,
Flag models and the lifecycle functions in `apps/postings/services.py`)

---

## 1. Purpose

Spec 001 built a complete, tested domain model and service layer with no way for a human
to exercise it except Django admin or `manage.py shell`. This feature adds the first web
layer to the project — HTTP views, URL routing, forms, and templates — so a poster can
create, confirm, and manage a posting, and a browser can find and view live postings, all
through an actual page in a browser.

This is deliberately the smallest complete vertical slice: create → confirm → browse →
view → manage. Nothing here introduces new persisted domain state.

---

## 2. User Stories

- As a poster, I want to fill out a form to create a posting for a site and category, so
  that I can list something without creating an account.
- As a poster, I want to confirm my posting after submitting it, so that it goes live.
- As a poster, I want a link that lets me view, renew, or delete my posting using my
  manage token, so that I retain control without an account.
- As a browser, I want to see a list of live postings for a site, optionally filtered by
  category, so that I can find what I'm looking for.
- As a browser, I want to view a single posting's details, so that I can decide whether to
  contact the poster.

---

## 3. Entities

No new persisted entities. This is a web layer on top of the models and service functions
from spec 001. `PostingImage` and `Flag` exist but are not touched by this feature.

One piece of non-domain infrastructure: a `seed_dev_data` management command that creates
a small, fixed set of dev-only `Site`/`Channel`/`Category` rows through the existing
models — ordinary data for local development and testing, not real Craigslist taxonomy
(spec 001 §7 already deferred that as a separate follow-on task).

---

## 4. Functional Requirements

### 4.1 Ubiquitous

- The system shall resolve the current site from the URL path (e.g. `/<site_slug>/...`),
  not from the request's Host header. Host-based resolution using `Site.hostname` is
  deferred to a later feature.
- The system shall render every page through Django templates extending one shared base
  template.
- The system shall use HTMX only for isolated interactive enhancements (e.g. a delete
  confirmation, a renew action), not for wholesale fragment-swapping of full pages.
- The system shall never display a posting's manage token anywhere except on the response
  immediately following an action that already required possessing that token (creation,
  or a manage-page request that already supplied a valid token).
- The system shall return 404, not 403, for a manage-page request with an unresolvable
  `public_id` or a non-matching token, using `get_posting_for_management` (CLAUDE.md §8).

### 4.2 Event-Driven

- WHEN a poster submits the create-posting form THE system SHALL call `create_posting()`
  and, on success, immediately call `submit_posting()`, transitioning the new posting to
  `PENDING`.
- WHEN a posting is submitted THE system SHALL render a confirmation page that displays
  the confirm link directly, rather than sending an email (see §8, Resolved Decisions).
- WHEN a poster follows the confirm link THE system SHALL call `confirm_posting()` and, on
  success, redirect to the posting's detail page.
- WHEN a poster requests their manage page with a valid `public_id` and token THE system
  SHALL display the posting's current status, its expiry (if any), and the actions
  available for that status.
- WHEN a poster requests delete from the manage page THE system SHALL call
  `delete_posting()` and redisplay the manage page reflecting the `DELETED` status.
- WHEN a poster requests renew from the manage page THE system SHALL call
  `renew_posting()` and redisplay the manage page reflecting the updated status and
  expiry.
- WHEN a browser requests the browse page for a site THE system SHALL list postings from
  `Posting.objects.visible()` filtered to that site, ordered newest-published-first,
  optionally filtered further by a category selected in the request.
- WHEN a browser requests a posting's detail page by `public_id` THE system SHALL display
  it if it is in `Posting.objects.visible()`, and return 404 otherwise (matching spec 001
  §5.3's "publicly reachable" rule).

### 4.3 State-Driven

- WHILE a posting is `DRAFT` or `PENDING` THE system SHALL NOT make it reachable from the
  browse page or its public detail URL.
- WHILE a posting is `ACTIVE` THE system SHALL show a renew action and a delete action on
  its manage page.
- WHILE a posting is `EXPIRED` THE system SHALL show a renew action (per spec 001 §5.3)
  and a delete action on its manage page, and SHALL NOT show it on the browse page or its
  public detail URL.
- WHILE a posting is `DELETED`, `HIDDEN`, or `BLOCKED` THE system SHALL show its terminal
  status on the manage page with no renew or delete action, and SHALL NOT make it
  reachable from the browse page or its public detail URL.

### 4.4 Unwanted Behavior

- IF `create_posting()` raises `InvalidCategoryAssignment`, `InvalidPriceForPolicy`, or
  `AreaRequired` THEN THE system SHALL redisplay the create form with the corresponding
  field-level error and the poster's other entered values preserved.
- IF `confirm_posting()` raises `ConfirmationExpired` THEN THE system SHALL display a
  message directing the poster to repost, without retrying the transition.
- IF a manage-page action raises `InvalidTransition`, `RenewalTooSoon`, or
  `RenewalWindowExpired` THEN THE system SHALL redisplay the manage page with that error
  message and no state change.
- IF the browse page or the create-posting form is requested for a site slug that does not
  exist or is not active THEN THE system SHALL return 404.

### 4.5 Optional Features

- WHERE a site has one or more areas THE system SHALL show an area selector on the
  create-posting form and SHALL treat it as required, consistent with spec 001 §5.5.
- WHERE a category's `price_policy` is `required` or `forbidden` THE system SHALL adjust
  the create-posting form's price field accordingly (required, or hidden/disabled),
  consistent with spec 001 §5.5.

---

## 5. Non-Functional Requirements

- The browse page shall stay within the query budget spec 001 §6 sets for a page of
  postings (no more than 3 database queries, including image prefetch — though this
  feature renders no images).
- No page in this feature shall require JavaScript beyond what HTMX itself loads; every
  action shall degrade to a full page reload if HTMX is unavailable.

---

## 6. Out of Scope

Explicitly not part of this feature. Do not implement, and do not scaffold in
anticipation:

- Sending any real email (the confirm link is shown directly per §4.2 and §8).
- Editing a posting's fields after creation — the manage page is view/renew/delete only.
- Image upload or display (`PostingImage`, `add_posting_image()` are untouched).
- Full-text or relevance search; the browse page's category filter is a plain equality
  filter, not search.
- The moderation review interface, flag submission, or any `block_posting()` call site.
- User accounts, authentication, or sessions.
- Host-based site resolution via `Site.hostname`; map rendering; geographic radius
  queries.
- Seeding real Craigslist category taxonomy — `seed_dev_data` is dev/test convenience data
  only.

---

## 7. Acceptance Verification

This feature is complete when:

1. Every requirement in §4 has at least one test asserting it (view-level tests using
   Django's test client).
2. Every rejected/error path in §4.4 has a test asserting the correct redisplay or
   response, not only the happy path.
3. `uv run pytest` passes and coverage on `apps/` remains ≥ 80%.
4. A poster can, in a real browser, create a posting, confirm it, see it on the browse
   page and its detail page, and delete or renew it from the manage page — verified
   manually, not only test-asserted.
5. `seed_dev_data` produces enough site/channel/category data for the walkthrough in (4)
   with no other setup.

---

## 8. Resolved Decisions

Resolved with the user before this spec was written:

1. **Confirmation is shown in-page, not emailed.** Spec 001 built `PENDING` and the
   72-hour confirmation window around an eventual email step; this feature exercises that
   same state machine but substitutes a directly-displayed link for the email itself.
   Called out explicitly because it measurably weakens the email-ownership guarantee
   `PENDING` was designed around — a later feature is expected to replace this with real
   email delivery without changing the underlying state machine.
2. **Site resolution is path-based, not host-based**, for this feature. `Site.hostname`
   remains in the schema for a later feature to use; no `ALLOWED_HOSTS` or
   host-resolution middleware changes are made here.
3. **The manage page does not support editing.** `delete_posting()` and `renew_posting()`
   map directly onto existing services with no new validation; a full edit form would
   need to re-run `create_posting()`'s category/price-policy/area validation against
   changed fields, which is deferred as its own scope.
4. **Seed data is a management command**, not a data migration or README instructions —
   reproducible and testable, and clearly separated from real migrations, which should
   never carry mutable fixture data.
5. **This feature is one bundled spec**, not split into separate create/browse specs —
   browse is one queryset and one template on top of postings that already exist once
   create is built, and splitting it out would mean fabricating test postings just to
   exercise browse in isolation. This mirrors how spec 001 bundled all nine lifecycle
   transitions into a single feature rather than one spec per transition.
