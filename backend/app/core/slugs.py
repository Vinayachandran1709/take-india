"""Public storefront names that must not be assigned to merchants."""

RESERVED_SLUGS = frozenset(
    {
        "admin", "api", "app", "auth", "billing", "booking", "bookings",
        "contact", "dashboard", "help", "login", "manage", "payments",
        "privacy", "pricing", "signup", "staff", "support", "terms",
        "typein", "webhook", "webhooks", "www",
    }
)


def is_reserved_slug(slug: str) -> bool:
    return slug.lower() in RESERVED_SLUGS
