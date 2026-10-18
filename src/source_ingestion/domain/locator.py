"""Locator canonicalization and SSRF destination policy (A-RULE-013, CT-SRC-001, CT-SEC-003).

Pure domain code without DNS or socket I/O: callers inject a resolver and must re-run
validate_destination for every redirect hop before connecting.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str], Iterable[str]]

ALLOWED_SCHEMES = frozenset({'http', 'https'})
DEFAULT_PORTS = {'http': 80, 'https': 443}
METADATA_ADDRESSES = frozenset({ipaddress.ip_address('169.254.169.254'), ipaddress.ip_address('fd00:ec2::254')})
_HOSTNAME_RE = re.compile(r'[a-z0-9_-]+(?:[.][a-z0-9_-]+)*')
_DIGITS = {8: frozenset('01234567'), 10: frozenset('0123456789'), 16: frozenset('0123456789abcdefABCDEF')}


class LocatorError(ValueError):
    """Rejected locator; the message is only the reason code and never echoes the raw locator."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnsupportedSchemeError(LocatorError):
    """Scheme other than http or https."""


class UnsafeDestinationError(LocatorError):
    """Host or address blocked by the SSRF policy."""


@dataclass(frozen=True)
class ValidatedLocator:
    locator: str
    host: str
    addresses: tuple[IPAddress, ...]


def _parse_ipv4_part(part: str) -> int | None:
    base = 10
    if part[:2] in ('0x', '0X'):
        base, part = 16, part[2:]
        if not part:
            return 0
    elif len(part) > 1 and part.startswith('0'):
        base, part = 8, part[1:]
    if not part or not set(part) <= _DIGITS[base]:
        return None
    return int(part, base)


def _legacy_ipv4(host: str) -> ipaddress.IPv4Address | None:
    parts = host.split('.')
    if len(parts) > 1 and parts[-1] == '':
        parts.pop()
    last_part = parts[-1]
    if not last_part or (_parse_ipv4_part(last_part) is None and not set(last_part) <= _DIGITS[10]):
        return None
    numbers = [_parse_ipv4_part(part) for part in parts]
    if len(numbers) > 4 or None in numbers:
        raise UnsafeDestinationError('AMBIGUOUS_NUMERIC_HOST')
    *head, last = numbers
    if any(number > 255 for number in head) or last >= 256 ** (5 - len(numbers)):
        raise UnsafeDestinationError('AMBIGUOUS_NUMERIC_HOST')
    value = last
    for index, number in enumerate(head):
        value += number << (8 * (3 - index))
    return ipaddress.IPv4Address(value)


def _ip_literal(host: str) -> IPAddress | None:
    candidate = host[1:-1] if host.startswith('[') and host.endswith(']') else host
    if ':' in candidate:
        try:
            return ipaddress.IPv6Address(candidate)
        except ValueError:
            raise LocatorError('INVALID_HOST') from None
    try:
        return ipaddress.IPv4Address(candidate)
    except ValueError:
        return _legacy_ipv4(candidate)


def _is_local_name(name: str) -> bool:
    name = name.lower().removesuffix('.')
    return name == 'localhost' or name.endswith('.localhost')


def _check_address(address: IPAddress) -> None:
    if address in METADATA_ADDRESSES:
        raise UnsafeDestinationError('METADATA_ADDRESS')
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            raise UnsafeDestinationError('IPV4_MAPPED_ADDRESS')
        if address.sixtofour is not None:
            _check_address(address.sixtofour)
    for reason, blocked in (
        ('UNSPECIFIED_ADDRESS', address.is_unspecified),
        ('LOOPBACK_ADDRESS', address.is_loopback),
        ('LINK_LOCAL_ADDRESS', address.is_link_local),
        ('MULTICAST_ADDRESS', address.is_multicast),
        ('RESERVED_ADDRESS', address.is_reserved),
        ('PRIVATE_ADDRESS', address.is_private),
        ('NON_GLOBAL_ADDRESS', not address.is_global),
    ):
        if blocked:
            raise UnsafeDestinationError(reason)


def _canonical_host(hostname: str) -> str:
    if '%' in hostname:
        raise LocatorError('INVALID_HOST')
    if ':' in hostname:
        return _ip_literal(hostname).compressed
    try:
        ascii_host = hostname.encode('idna').decode('ascii').lower().removesuffix('.')
    except UnicodeError:
        raise LocatorError('INVALID_HOST') from None
    literal = _ip_literal(ascii_host)
    if literal is not None:
        return literal.compressed
    if len(ascii_host) > 253 or not _HOSTNAME_RE.fullmatch(ascii_host):
        raise LocatorError('INVALID_HOST')
    return ascii_host


def canonicalize_locator(raw: str) -> str:
    """Canonical http(s) locator: lowercase IDNA host, no fragment, no default port, path at least '/'."""
    if not isinstance(raw, str) or not raw.strip():
        raise LocatorError('INVALID_LOCATOR')
    text = raw.strip()
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in text):
        raise LocatorError('INVALID_LOCATOR')
    try:
        parts = urlsplit(text)
    except ValueError:
        raise LocatorError('INVALID_LOCATOR') from None
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsupportedSchemeError('UNSUPPORTED_SCHEME')
    if parts.username is not None or parts.password is not None:
        raise LocatorError('CREDENTIALS_IN_LOCATOR')
    if not parts.hostname:
        raise LocatorError('MISSING_HOST')
    try:
        port = parts.port
    except ValueError:
        raise LocatorError('INVALID_PORT') from None
    if port == 0:
        raise LocatorError('INVALID_PORT')
    host = _canonical_host(parts.hostname)
    netloc = f'[{host}]' if ':' in host else host
    if port is not None and port != DEFAULT_PORTS[scheme]:
        netloc = f'{netloc}:{port}'
    return urlunsplit((scheme, netloc, parts.path or '/', parts.query, ''))


def validate_destination(host: str, resolved_ips: Iterable[str | IPAddress]) -> tuple[IPAddress, ...]:
    """Fail-closed SSRF check of the host and every resolved address; returns the addresses to pin."""
    if not isinstance(host, str) or not host:
        raise LocatorError('MISSING_HOST')
    name = host.lower().removesuffix('.')
    literal = _ip_literal(name)
    if literal is None and _is_local_name(name):
        raise UnsafeDestinationError('LOCALHOST_NAME')
    addresses: list[IPAddress] = [] if literal is None else [literal]
    for value in resolved_ips:
        if isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            addresses.append(value)
            continue
        try:
            addresses.append(ipaddress.ip_address(value if isinstance(value, str) else ''))
        except ValueError:
            raise UnsafeDestinationError('INVALID_RESOLVED_ADDRESS') from None
    if not addresses:
        raise UnsafeDestinationError('UNRESOLVED_HOST')
    for address in addresses:
        _check_address(address)
    return tuple(addresses)


def validate_locator(raw: str, resolver: Resolver) -> ValidatedLocator:
    """Canonicalize, resolve names only through the injected resolver, then validate every address."""
    locator = canonicalize_locator(raw)
    host = urlsplit(locator).hostname or ''
    resolved: tuple[str, ...] = ()
    if _ip_literal(host) is None:
        if _is_local_name(host):
            raise UnsafeDestinationError('LOCALHOST_NAME')
        try:
            resolved = tuple(resolver(host))
        except OSError:
            raise UnsafeDestinationError('RESOLUTION_FAILED') from None
    return ValidatedLocator(locator, host, validate_destination(host, resolved))
