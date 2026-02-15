"""Core redaction engine for IPv4, IPv6, and MAC addresses."""

import hmac
import re
import secrets
import uuid
from hashlib import sha256
from typing import Optional

from .models import RedactMode

# --- Compiled regex patterns (immutable, ReDoS-safe) ---

# IPv6: must be matched before IPv4 to handle ::ffff:x.x.x.x forms
# Covers: full form, compressed (::), ::ffff:mapped, loopback (::1)
IPV6_RE = re.compile(
    r"(?<![:\w])"
    r"("
    # ::ffff:IPv4-mapped
    r"::ffff:(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"|"
    # Full form: 8 groups of 1-4 hex digits
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|"
    # Compressed forms with ::
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}"
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}"
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}"
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}"
    r"|"
    r"[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}"
    r"|"
    # :: with trailing groups
    r":(?::[0-9a-fA-F]{1,4}){1,7}"
    r"|"
    # Leading groups with trailing ::
    r"(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|"
    # Just ::
    r"::"
    r")"
    r"(?![:\w])",
)

# IPv4: four bounded octets (0-255) with word boundaries
IPV4_RE = re.compile(
    r"\b"
    r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"\b"
)

# MAC: six hex pairs with : or - separators
MAC_RE = re.compile(
    r"\b([0-9a-fA-F]{2}(?:[:\-])){5}[0-9a-fA-F]{2}\b"
)

# Pattern processing order: IPv6 first to prevent partial IPv4 matches
PATTERNS = [
    ("ipv6", IPV6_RE),
    ("ipv4", IPV4_RE),
    ("mac", MAC_RE),
]


class RedactorEngine:
    """Per-request redaction engine. No shared mutable state between instances."""

    def __init__(
        self,
        mode: RedactMode = RedactMode.random,
        deterministic_secret: Optional[bytes] = None,
        deterministic_context: str = "default",
    ) -> None:
        self.mapping_id = uuid.uuid4()
        self.mode = mode
        self._mapping: dict[str, str] = {}
        if mode == RedactMode.deterministic:
            if deterministic_secret is None:
                raise ValueError("Deterministic mode requires a secret key")
            context_bytes = deterministic_context.encode("utf-8")
            self._deterministic_key = sha256(deterministic_secret + context_bytes).digest()
        else:
            self._deterministic_key = None

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        """Redact all sensitive patterns from text.

        Returns (redacted_text, mapping_dict).
        """
        result = text
        for pattern_type, pattern in PATTERNS:
            result = pattern.sub(
                lambda m, pt=pattern_type: self._replace(m.group(0), pt),
                result,
            )
        return result, dict(self._mapping)

    def _replace(self, original: str, pattern_type: str) -> str:
        """Get or create a replacement for the original value."""
        if original in self._mapping:
            return self._mapping[original]

        if self.mode == RedactMode.deterministic:
            replacement = self._deterministic_replacement(original, pattern_type)
        else:
            replacement = self._random_replacement(pattern_type)

        self._mapping[original] = replacement
        return replacement

    def _deterministic_replacement(self, original: str, pattern_type: str) -> str:
        """HMAC-SHA256 derived replacement — consistent within request, different across requests."""
        assert self._deterministic_key is not None  # For type checkers
        digest = hmac.new(self._deterministic_key, original.encode(), sha256).digest()
        if pattern_type == "ipv4":
            return self._ipv4_from_bytes(digest)
        elif pattern_type == "ipv6":
            return self._ipv6_from_bytes(digest)
        else:
            return self._mac_from_bytes(digest)

    def _random_replacement(self, pattern_type: str) -> str:
        """Cryptographically random replacement."""
        if pattern_type == "ipv4":
            return self._random_ipv4()
        elif pattern_type == "ipv6":
            return self._random_ipv6()
        else:
            return self._random_mac()

    @staticmethod
    def _random_ipv4() -> str:
        octets = [secrets.randbelow(256) for _ in range(4)]
        return f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"

    @staticmethod
    def _random_ipv6() -> str:
        groups = [secrets.randbelow(0x10000) for _ in range(8)]
        return ":".join(f"{g:04x}" for g in groups)

    @staticmethod
    def _random_mac() -> str:
        octets = [secrets.randbelow(256) for _ in range(6)]
        return ":".join(f"{o:02x}" for o in octets)

    @staticmethod
    def _ipv4_from_bytes(data: bytes) -> str:
        return f"{data[0]}.{data[1]}.{data[2]}.{data[3]}"

    @staticmethod
    def _ipv6_from_bytes(data: bytes) -> str:
        groups = []
        for i in range(8):
            val = (data[i * 2] << 8) | data[i * 2 + 1]
            groups.append(f"{val:04x}")
        return ":".join(groups)

    @staticmethod
    def _mac_from_bytes(data: bytes) -> str:
        return ":".join(f"{data[i]:02x}" for i in range(6))
