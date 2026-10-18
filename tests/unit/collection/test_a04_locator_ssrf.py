"""A-04: canonical locator and SSRF destination policy.

coveredIds: A-RULE-013, CT-SRC-001, CT-SEC-003
"""
import ast
import ipaddress
import pathlib
import socket
from urllib.parse import urlsplit

import pytest

from source_ingestion.domain.locator import (
    LocatorError,
    UnsafeDestinationError,
    UnsupportedSchemeError,
    ValidatedLocator,
    canonicalize_locator,
    validate_destination,
    validate_locator,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCATOR_MODULE = ROOT / 'src' / 'source_ingestion' / 'domain' / 'locator.py'
ALLOWED_IMPORTS = frozenset({'__future__', 'collections.abc', 'dataclasses', 'ipaddress', 're', 'urllib.parse'})
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')


def _network_forbidden(*args, **kwargs):
    raise AssertionError('real DNS/network call in unit test')


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


class FakeResolver:
    def __init__(self, table=None, error=None) -> None:
        self.table = table or {}
        self.error = error
        self.calls: list[str] = []

    def __call__(self, host: str) -> list[str]:
        self.calls.append(host)
        if self.error is not None:
            raise self.error
        return list(self.table.get(host, []))


def test_network_guard_blocks_real_dns_and_connect() -> None:
    with pytest.raises(AssertionError):
        socket.getaddrinfo('example.com', 443)
    with pytest.raises(AssertionError):
        socket.create_connection(('example.com', 443))


def test_locator_module_imports_no_network_modules() -> None:
    tree = ast.parse(LOCATOR_MODULE.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= ALLOWED_IMPORTS, sorted(imported - ALLOWED_IMPORTS)


@pytest.mark.parametrize(('raw', 'expected'), [
    ('HTTPS://Example.COM:443/a/b?x=1#frag', 'https://example.com/a/b?x=1'),
    ('http://example.com:80', 'http://example.com/'),
    ('http://example.com:8080/p', 'http://example.com:8080/p'),
    ('https://example.com:80/', 'https://example.com:80/'),
    ('http://example.com:443/', 'http://example.com:443/'),
    ('https://BÜcher.example/path', 'https://xn--bcher-kva.example/path'),
    ('http://example.com./', 'http://example.com/'),
    ('  https://example.com/x#  ', 'https://example.com/x'),
    ('http://0x7f000001/', 'http://127.0.0.1/'),
    ('http://127.1/', 'http://127.0.0.1/'),
    ('http://2130706433/', 'http://127.0.0.1/'),
])
def test_canonicalize_locator_normalizes(raw: str, expected: str) -> None:
    assert canonicalize_locator(raw) == expected
    assert canonicalize_locator(expected) == expected


def test_canonicalize_locator_normalizes_ipv6_literal() -> None:
    result = canonicalize_locator('http://[::FFFF:127.0.0.1]:80/#x')
    assert result.startswith('http://[') and result.endswith(']/')
    assert ipaddress.ip_address(urlsplit(result).hostname) == ipaddress.ip_address('::ffff:7f00:1')
    assert canonicalize_locator(result) == result


@pytest.mark.parametrize('raw', [
    'file:///etc/passwd', 'ftp://example.com/', 'gopher://example.com/',
    'javascript:alert(1)', 'ws://example.com/', 'example.com/path',
])
def test_canonicalize_locator_rejects_non_http_schemes(raw: str) -> None:
    with pytest.raises(UnsupportedSchemeError) as caught:
        canonicalize_locator(raw)
    assert caught.value.reason == 'UNSUPPORTED_SCHEME'


@pytest.mark.parametrize(('raw', 'reason'), [
    ('', 'INVALID_LOCATOR'),
    ('http://exa mple.com/', 'INVALID_LOCATOR'),
    ('http:///path', 'MISSING_HOST'),
    ('http://example.com:99999/', 'INVALID_PORT'),
    ('http://example.com:0/', 'INVALID_PORT'),
    ('http://a..b/', 'INVALID_HOST'),
    ('http://exa!mple.com/', 'INVALID_HOST'),
    ('http://1.2.3.4.5/', 'AMBIGUOUS_NUMERIC_HOST'),
    ('http://256.0.0.1/', 'AMBIGUOUS_NUMERIC_HOST'),
])
def test_canonicalize_locator_rejects_malformed(raw: str, reason: str) -> None:
    with pytest.raises(LocatorError) as caught:
        canonicalize_locator(raw)
    assert caught.value.reason == reason


def test_canonicalize_locator_rejects_non_string() -> None:
    with pytest.raises(LocatorError) as caught:
        canonicalize_locator(None)
    assert caught.value.reason == 'INVALID_LOCATOR'


def test_canonicalize_locator_rejects_credentials_without_echoing_them() -> None:
    with pytest.raises(LocatorError) as caught:
        canonicalize_locator('https://user:s3cr3t-token@example.com/feed')
    assert caught.value.reason == 'CREDENTIALS_IN_LOCATOR'
    assert 's3cr3t-token' not in str(caught.value)


@pytest.mark.parametrize(('host', 'reason'), [
    ('127.0.0.1', 'LOOPBACK_ADDRESS'),
    ('127.1', 'LOOPBACK_ADDRESS'),
    ('2130706433', 'LOOPBACK_ADDRESS'),
    ('0x7f000001', 'LOOPBACK_ADDRESS'),
    ('0177.0.0.1', 'LOOPBACK_ADDRESS'),
    ('::1', 'LOOPBACK_ADDRESS'),
    ('[::1]', 'LOOPBACK_ADDRESS'),
    ('10.0.0.1', 'PRIVATE_ADDRESS'),
    ('172.16.0.1', 'PRIVATE_ADDRESS'),
    ('192.168.1.1', 'PRIVATE_ADDRESS'),
    ('fc00::1', 'PRIVATE_ADDRESS'),
    ('169.254.169.254', 'METADATA_ADDRESS'),
    ('169.254.1.1', 'LINK_LOCAL_ADDRESS'),
    ('fe80::1', 'LINK_LOCAL_ADDRESS'),
    ('224.0.0.1', 'MULTICAST_ADDRESS'),
    ('ff02::1', 'MULTICAST_ADDRESS'),
    ('240.0.0.1', 'RESERVED_ADDRESS'),
    ('0.0.0.0', 'UNSPECIFIED_ADDRESS'),
    ('::', 'UNSPECIFIED_ADDRESS'),
    ('::ffff:127.0.0.1', 'IPV4_MAPPED_ADDRESS'),
    ('[::ffff:7f00:1]', 'IPV4_MAPPED_ADDRESS'),
    ('::ffff:8.8.8.8', 'IPV4_MAPPED_ADDRESS'),
    ('2002:7f00:1::', 'LOOPBACK_ADDRESS'),
    ('100.64.0.1', 'NON_GLOBAL_ADDRESS'),
])
def test_validate_destination_blocks_unsafe_literals(host: str, reason: str) -> None:
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_destination(host, ())
    assert caught.value.reason == reason


def test_validate_destination_accepts_public_addresses() -> None:
    assert validate_destination('example.com', ['8.8.8.8']) == (ipaddress.ip_address('8.8.8.8'),)
    assert validate_destination('example.com.', ['2001:4860:4860::8888']) == (
        ipaddress.ip_address('2001:4860:4860::8888'),
    )
    assert validate_destination('8.8.8.8', ()) == (ipaddress.ip_address('8.8.8.8'),)


@pytest.mark.parametrize(('host', 'resolved', 'reason'), [
    ('example.com', ['8.8.8.8', '10.0.0.5'], 'PRIVATE_ADDRESS'),
    ('example.com', ['127.0.0.1'], 'LOOPBACK_ADDRESS'),
    ('example.com', [], 'UNRESOLVED_HOST'),
    ('example.com', ['not-an-ip'], 'INVALID_RESOLVED_ADDRESS'),
    ('example.com', ['2130706433'], 'INVALID_RESOLVED_ADDRESS'),
    ('localhost', ['8.8.8.8'], 'LOCALHOST_NAME'),
    ('api.LOCALHOST', ['8.8.8.8'], 'LOCALHOST_NAME'),
    ('8.8.8.8', ['127.0.0.1'], 'LOOPBACK_ADDRESS'),
])
def test_validate_destination_blocks_unsafe_resolution(host: str, resolved: list[str], reason: str) -> None:
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_destination(host, resolved)
    assert caught.value.reason == reason


def test_validate_locator_uses_injected_resolver_for_names() -> None:
    resolver = FakeResolver({'example.com': ['8.8.8.8']})
    result = validate_locator('HTTPS://Example.com:443/feed#top', resolver)
    assert result == ValidatedLocator('https://example.com/feed', 'example.com', (ipaddress.ip_address('8.8.8.8'),))
    assert resolver.calls == ['example.com']


@pytest.mark.parametrize(('raw', 'reason'), [
    ('http://127.1/', 'LOOPBACK_ADDRESS'),
    ('http://0x7f000001/', 'LOOPBACK_ADDRESS'),
    ('http://2130706433/', 'LOOPBACK_ADDRESS'),
    ('http://[::ffff:127.0.0.1]/', 'IPV4_MAPPED_ADDRESS'),
    ('http://169.254.169.254/latest/meta-data/', 'METADATA_ADDRESS'),
])
def test_validate_locator_blocks_ip_literals_without_dns(raw: str, reason: str) -> None:
    resolver = FakeResolver({})
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_locator(raw, resolver)
    assert caught.value.reason == reason
    assert resolver.calls == []


def test_validate_locator_rejects_file_scheme_before_resolution() -> None:
    resolver = FakeResolver({})
    with pytest.raises(UnsupportedSchemeError):
        validate_locator('file:///etc/passwd', resolver)
    assert resolver.calls == []


def test_validate_locator_blocks_rebinding_answer() -> None:
    resolver = FakeResolver({'rebind.example': ['8.8.8.8', '127.0.0.1']})
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_locator('http://rebind.example/', resolver)
    assert caught.value.reason == 'LOOPBACK_ADDRESS'


def test_validate_locator_fails_closed_on_resolver_error() -> None:
    resolver = FakeResolver(error=socket.gaierror('fake resolver failure'))
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_locator('https://example.com/', resolver)
    assert caught.value.reason == 'RESOLUTION_FAILED'


def test_validate_locator_rejects_localhost_without_resolving() -> None:
    resolver = FakeResolver({'localhost': ['8.8.8.8']})
    with pytest.raises(UnsafeDestinationError) as caught:
        validate_locator('http://localhost:8080/', resolver)
    assert caught.value.reason == 'LOCALHOST_NAME'
    assert resolver.calls == []
