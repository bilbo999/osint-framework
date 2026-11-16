"""Syntactic input validation for target values.

Only *syntax* is checked here (is this shaped like a domain/email/...?). Canonical
normalization (IDNA, lower-casing, E.164, ...) belongs to app.analyzers.normalizers
(Phase 4a) and must record NormalizationStep entries.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from urllib.parse import urlsplit

from app.domain.enums import TargetType

_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()./-]{6,32}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def is_valid_domain(value: str) -> bool:
    """Return True for a syntactically valid (optionally internationalised) hostname."""
    candidate = value.strip().rstrip(".")
    if not candidate or len(candidate) > 253:
        return False
    try:
        ascii_form = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return False
    labels = ascii_form.split(".")
    if len(labels) < 2:
        return False
    return all(_LABEL_RE.match(label) for label in labels)


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return True


def is_valid_email(value: str) -> bool:
    candidate = value.strip()
    if candidate.count("@") != 1:
        return False
    local, domain = candidate.split("@")
    if not local or len(local) > 64 or any(c.isspace() for c in local):
        return False
    return is_valid_domain(domain)


def is_valid_url(value: str) -> bool:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    return is_valid_domain(parts.hostname) or is_valid_ip(parts.hostname)


def is_valid_username(value: str) -> bool:
    return bool(_USERNAME_RE.match(value.strip()))


def is_valid_phone(value: str) -> bool:
    candidate = value.strip()
    digits = sum(c.isdigit() for c in candidate)
    return bool(_PHONE_RE.match(candidate)) and 6 <= digits <= 15


def is_valid_free_text(value: str) -> bool:
    """Names of people/organisations: printable, non-empty, bounded."""
    candidate = value.strip()
    return 0 < len(candidate) <= 256 and not _CONTROL_RE.search(candidate)


VALIDATORS: dict[TargetType, Callable[[str], bool]] = {
    TargetType.PERSON: is_valid_free_text,
    TargetType.ORGANIZATION: is_valid_free_text,
    TargetType.DOMAIN: is_valid_domain,
    TargetType.IP_ADDRESS: is_valid_ip,
    TargetType.EMAIL: is_valid_email,
    TargetType.USERNAME: is_valid_username,
    TargetType.PHONE: is_valid_phone,
    TargetType.URL: is_valid_url,
}


def validate_target_value(target_type: TargetType, value: str) -> bool:
    return VALIDATORS[target_type](value)
