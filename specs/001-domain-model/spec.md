# Spec 001: Domain Model & Posting Lifecycle

**Status:** Draft — awaiting review
**Depends on:** Nothing (first feature)

---

## 1. Purpose

Establish the persistent domain model for the classifieds platform and the state machine
governing a posting's life from creation through expiry, deletion, or moderation removal.

This is the foundation every later feature builds on. Getting the lifecycle wrong here is
expensive: browse, search, expiry jobs, and moderation all filter on posting state, and a
sloppy state model leaks into all of them.

---

## 2. User Stories

- As a **poster**, I want to create a posting scoped to a geographic site and a category,
  so that it reaches people near me who are looking for what I have.
- As a **poster**, I want a secret link that lets me edit, renew, or delete my posting
  without creating an account, so that posting is low-friction.
- As a **poster**, I want my posting to expire automatically, so that I am not
  responsible for cleaning up stale ads.
- As a **browser**, I want to see only live postings, so that I do not waste time on
  expired, deleted, or removed content.
- As a **platform operator**, I want removed postings retained rather than hard-deleted,
  so that abuse patterns remain auditable.

---

## 3. Entities

Field lists here are the *contract*. Types, indexes, and constraints are decided in
`plan.md`.

### Site
A geographic region with its own subdomain. Example: `houston`.
Fields: `slug`, `name`, `hostname`, `timezone`, `latitude`, `longitude`, `is_active`.

### Area
An optional subdivision of a Site. Example: `katy` within `houston`.
Fields: `site` (FK), `slug`, `name`, `sort_order`.

### Channel
A top-level grouping. Examples: for sale, housing, jobs, services, community.
Fields: `slug`, `name`, `sort_order`.

### Category
A leaf under a Channel, identified by a short code. Example: `cto` (cars & trucks by owner).
Fields: `channel` (FK), `code`, `slug`, `name`, `sort_order`, `lifetime_days`,
`price_policy`, `is_active`.

`price_policy` is one of: `required`, `optional`, `forbidden`.

### Posting
The central entity.
Fields: `public_id`, `site` (FK), `area` (FK, nullable), `category` (FK), `title`, `body`,
`price`, `contact_email`, `contact_name`, `contact_phone`, `show_phone`, `location_text`,
`latitude`, `longitude`, `status`, `manage_token_hash`, `created_at`, `published_at`,
`expires_at`, `last_renewed_at`, `updated_at`, `removed_at`, `reposted_from` (self FK,
nullable).

### PostingImage
Fields: `posting` (FK), `image`, `sort_order`, `created_at`.

### Flag
A community report against a posting.
Fields: `posting` (FK), `reason`, `reporter_fingerprint`, `created_at`.

---

## 4. Posting Status Values

| Status | Meaning |
|---|---|
| `DRAFT` | Created but not yet submitted for confirmation |
| `PENDING` | Awaiting email confirmation from the poster |
| `ACTIVE` | Live and publicly visible |
| `EXPIRED` | Passed its expiry date |
| `DELETED` | Removed by the poster |
| `HIDDEN` | Auto-hidden by flag threshold, pending review |
| `BLOCKED` | Removed by an operator |

---

## 5. Functional Requirements

### 5.1 Ubiquitous

- The system shall assign every posting a `public_id` that is unique, non-sequential,
  and distinct from the database primary key.
- The system shall store all timestamps in UTC.
- The system shall associate every posting with exactly one Site, exactly one Category,
  and at most one Area.
- The system shall store only a hash of the manage token, never the plaintext.
- The system shall retain every posting row permanently; no status transition shall
  delete a row.
- The system shall expose a single canonical queryset representing publicly visible
  postings, and every browse or search feature shall derive from it.

### 5.2 Event-Driven

- WHEN a posting is created THE system SHALL set status to `DRAFT`, generate a manage
  token, and return the plaintext token exactly once.
- WHEN a posting is submitted THE system SHALL transition `DRAFT` → `PENDING` and record
  the submission time.
- WHEN a posting is confirmed THE system SHALL transition `PENDING` → `ACTIVE`, set
  `published_at` to the current time, and set `expires_at` to `published_at` plus the
  category's `lifetime_days`.
- WHEN a posting is renewed THE system SHALL set `expires_at` to the current time plus
  the category's `lifetime_days`, and set `last_renewed_at` to the current time.
- WHEN the expiry job runs THE system SHALL transition every `ACTIVE` posting whose
  `expires_at` has passed to `EXPIRED`.
- WHEN a poster deletes a posting THE system SHALL transition it to `DELETED` and set
  `removed_at`.
- WHEN the count of distinct flags on an `ACTIVE` posting reaches the configured
  threshold THE system SHALL transition it to `HIDDEN` and set `removed_at`.
- WHEN a posting is reposted THE system SHALL create a new posting with a new
  `public_id` and a new manage token, and SHALL record the source posting in
  `reposted_from`.

### 5.3 State-Driven

- WHILE a posting is in any status other than `ACTIVE` THE system SHALL exclude it from
  the publicly visible queryset.
- WHILE a posting is `PENDING` THE system SHALL accept confirmation for 72 hours from
  submission, after which confirmation shall be refused.
- WHILE a posting is `ACTIVE` or `EXPIRED` THE system SHALL permit renewal, subject to
  the interval rule in §5.4.
- WHILE a posting is `BLOCKED` THE system SHALL reject all poster-initiated transitions,
  including delete and renew.
- WHILE a posting is not `ACTIVE`, THE system SHALL treat unauthenticated public lookup
  by `public_id` identically to a nonexistent posting; this does not affect poster access
  via the manage token.

### 5.4 Unwanted Behavior

- IF a renewal is attempted less than 48 hours after `published_at` or `last_renewed_at`,
  whichever is later, THEN THE system SHALL reject it with a `RenewalTooSoon` error.
- IF a renewal is attempted more than 7 days after `expires_at` THEN THE system SHALL
  reject it and direct the poster to repost.
- IF a supplied manage token does not match the stored hash THEN THE system SHALL behave
  identically to the case where the posting does not exist.
- IF a posting is assigned a Category that has child categories THEN THE system SHALL
  reject the assignment; postings attach only to leaf categories.
- IF a posting has more than 24 images THEN THE system SHALL reject the additional images.
- IF a price is negative THEN THE system SHALL reject the posting.
- IF a state transition is not permitted from the posting's current status THEN THE
  system SHALL raise an `InvalidTransition` error and leave the posting unchanged.
- IF the same reporter fingerprint flags the same posting more than once THEN THE system
  SHALL count it as a single flag.
- IF a repost is attempted without a valid manage token for the source posting THEN THE
  system SHALL reject it.

### 5.5 Optional Features

- WHERE a Category's `price_policy` is `required` THE system SHALL reject postings
  without a price.
- WHERE a Category's `price_policy` is `forbidden` THE system SHALL reject postings with
  a price.
- WHERE a Site has one or more Areas THE system SHALL require an Area on posting creation.
- WHERE a posting has coordinates THE system SHALL store them; WHERE it does not THE
  system SHALL still permit the posting.

---

## 6. Non-Functional Requirements

- Retrieving one page of postings for a Site and Category shall require no more than 3
  database queries, including image prefetch.
- The expiry job shall process 100,000 expired postings in under 60 seconds.
- The publicly visible queryset shall be index-backed on `(site, category, status,
  published_at)`.
- Manage tokens shall carry at least 128 bits of entropy from a cryptographically secure
  source.

---

## 7. Out of Scope

Explicitly not part of this feature. Do not implement, and do not scaffold in
anticipation:

- HTTP views, URL routing, forms, and templates
- Sending any email, including confirmation email and reply relay
- Image upload handling, storage backends, and resizing
- Full-text search and search indexing
- The moderation review interface
- User accounts and authentication
- Map rendering and geographic radius queries
- Seeding real Craigslist category taxonomy (a follow-on task)

The confirmation *transition* is in scope; the confirmation *email* is not. Model the
state machine so that a later feature can trigger it.

---

## 8. Acceptance Verification

This feature is complete when:

1. Every requirement in §5 has at least one test asserting it.
2. Every rejected transition in the state machine has a test asserting the rejection.
3. `uv run pytest` passes and coverage on `apps/` is ≥ 80%.
4. Migrations apply cleanly against an empty database.
5. A `tests/factories.py` exists that can construct a valid posting in any status.

---

## 9. Resolved Decisions

Resolved during the clarify pass, before `plan.md`:

1. **`lifetime_days` is per-Category only**, with no Site dimension. Simpler and matches
   the project's boring-is-correct bias; real Craigslist's per-market variation isn't a
   demonstrated need here. Adding a Site override later is cheap (additive override plus
   a resolver method) if that changes.
2. **The flag threshold is global**, not per-Category. One configured value is simplest;
   a per-Category override can be added later as a nullable field with fallback to the
   global default without breaking existing data.
3. **`EXPIRED` postings are not publicly reachable at their canonical URL.** "Publicly
   visible" and "publicly reachable" are the same queryset, preserving the single
   canonical queryset commitment in §5.1. This does not affect poster-side access, which
   goes through the manage token rather than the public URL.
4. **`reposted_from` is enforced as same-poster**, via possession of the source
   posting's manage token — consistent with how delete and renew are already authorized
   in this account-less model. This closes an easy provenance-spoofing vector at
   near-zero implementation cost.
