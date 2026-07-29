class PostingError(Exception):
    """Base class for domain errors raised by apps.postings.services."""


class InvalidTransition(PostingError):
    """Raised when a status transition is not permitted from the posting's current status."""


class ConfirmationExpired(PostingError):
    """Raised when confirmation is attempted more than 72 hours after submission."""


class RenewalTooSoon(PostingError):
    """Raised when renewal is attempted before the minimum renewal interval has elapsed."""


class RenewalWindowExpired(PostingError):
    """Raised when renewal is attempted too long after expiry; the poster must repost instead."""


class InvalidCategoryAssignment(PostingError):
    """Raised when a posting is assigned a Category that is not a leaf."""


class InvalidPriceForPolicy(PostingError):
    """Raised when a posting's price does not match its Category's price_policy."""


class AreaRequired(PostingError):
    """Raised when a Site has Areas but none was supplied on posting creation."""


class ImageLimitExceeded(PostingError):
    """Raised when a posting would exceed the maximum number of images."""
