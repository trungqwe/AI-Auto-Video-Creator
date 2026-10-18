"""A-12: SourceAdapter port and SecureFetcher SSRF boundary across redirects.

coveredIds: A-RULE-013, A-RULE-014
"""
import ast
import ipaddress
import logging
import pathlib
import socket
from datetime import datetime, timezone

import pytest

from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.adapters.secure_fetch import (
    INPUT_NOT_READY,
    FetchPolicy,
    SecureFetcher,
    TransportResponse,
    parse_retry_after,
    safe_headers,
)
from source_ingestion.ports.source_adapter import (
    CAPABILITY_UNAVAILABLE,
    AdapterDescriptor,
    AdapterOperation,
    CandidateListing,
    CapabilityUnavailable,
    FetchedDocument,
    ProbeResult,
    SourceAdapter,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULES = (
    ROOT / 'src' / 'source_ingestion' / 'ports' / 'source_adapter.py',
    ROOT / 'src' / 'source_ingestion' / 'adapters' / 'secure_fetch.py',
)
FORBIDDEN_IMPORTS = ('socket', 'ssl', 'http', 'urllib.request', 'requests', 'httpx', 'urllib3', 'aiohttp')
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
LOGGER = 'source_ingestion.adapters.secure_fetch'
NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
PUBLIC = '93.184.216.34'
SECRET = 'SECRET-VALUE-7f3a'


def _network_forbidden(*args, **kwargs):
    raise AssertionError('real DNS/network call in unit test')


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


def make_policy(**overrides):
    values = {
        'revision': 'fetch-policy-r1',
        'max_redirects': 3,
        'max_body_bytes': 1000,
        'allowed_media_types': frozenset({'text/html', 'application/rss+xml'}),
        'timeout_seconds': 10.0,
    }
    values.update(overrides)
    return FetchPolicy(**values)


class FakeResolver:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, host):
        self.calls.append(host)
        if host not in self.table:
            raise socket.gaierror('fake resolver: unknown host')
        return list(self.table[host])


class FakeClock:
    def __init__(self, step=0.0):
        self.now = 100.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


class CountingBody:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.consumed = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk

    def close(self):
        self.closed = True


class FakeTransport:
    """Scripted responses keyed by locator; records every request and opens no socket."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        route = self.routes[request.locator]
        if isinstance(route, BaseException):
            raise route
        return route


def response(status, headers=(), chunks=()):
    return TransportResponse(status, tuple(headers), CountingBody(chunks))


def html(body=b'<html>ok</html>', extra=()):
    return response(200, (('Content-Type', 'text/html; charset=utf-8'), *extra), (body,))


def redirect(location, status=302):
    return response(status, (('Location', location),))


def make_fetcher(routes, table=None, clock=None):
    transport = FakeTransport(routes)
    resolver = FakeResolver({'news.example': [PUBLIC]} if table is None else table)
    fetcher = SecureFetcher(transport, resolver, clock=clock or FakeClock(), utc_now=lambda: NOW)
    return fetcher, transport, resolver


def fetch(fetcher, locator='https://news.example/', **overrides):
    return fetcher.fetch(locator, make_policy(**overrides), correlation_id='corr-1')


def problem_code(result):
    assert isinstance(result, ProblemDetail), result
    return result.values['code']


def test_network_guard_blocks_real_dns_and_connect():
    with pytest.raises(AssertionError):
        socket.getaddrinfo('example.com', 443)
    with pytest.raises(AssertionError):
        socket.create_connection(('example.com', 443))


def test_modules_do_not_import_network_stack():
    for module in MODULES:
        imported = set()
        for node in ast.walk(ast.parse(module.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or '')
        bad = sorted(n for n in imported if any(n == p or n.startswith(p + '.') for p in FORBIDDEN_IMPORTS))
        assert bad == [], (module.name, bad)


class ProbeOnlyAdapter:
    """Fake adapter that supports only probe; every other operation is unavailable."""

    descriptor = AdapterDescriptor('fake-probe', '1', frozenset({AdapterOperation.PROBE}))

    def _unavailable(self, operation):
        return self.descriptor.unavailable(operation, 'NOT_SUPPORTED_BY_FAKE')

    def probe(self, locator):
        return ProbeResult(locator, self.descriptor)

    def list_candidates(self, locator, cursor):
        return self._unavailable(AdapterOperation.LIST_CANDIDATES)

    def fetch_document(self, locator):
        return self._unavailable(AdapterOperation.FETCH_DOCUMENT)

    def extract_candidate(self, document):
        return self._unavailable(AdapterOperation.EXTRACT_CANDIDATE)

    def resume_from_checkpoint(self, checkpoint_version, cursor):
        return self._unavailable(AdapterOperation.RESUME_FROM_CHECKPOINT)

    def supplemental_search(self, intent):
        return self._unavailable(AdapterOperation.SUPPLEMENTAL_SEARCH)


def test_source_adapter_protocol_declares_six_operations():
    expected = [
        'probe', 'list_candidates', 'fetch_document', 'extract_candidate', 'resume_from_checkpoint',
        'supplemental_search',
    ]
    assert [operation.value for operation in AdapterOperation] == expected
    assert all(callable(getattr(SourceAdapter, name)) for name in expected)
    assert isinstance(ProbeOnlyAdapter(), SourceAdapter)


def test_missing_capability_is_structured_not_empty_success():
    adapter = ProbeOnlyAdapter()
    listing = adapter.list_candidates('https://news.example/', None)
    assert isinstance(listing, CapabilityUnavailable) and not isinstance(listing, CandidateListing)
    assert (listing.code, listing.operation, listing.adapter_id, listing.adapter_version, listing.retryable) == (
        CAPABILITY_UNAVAILABLE, AdapterOperation.LIST_CANDIDATES, 'fake-probe', '1', False,
    )
    assert adapter.descriptor.supports(AdapterOperation.PROBE)
    assert not adapter.descriptor.supports(AdapterOperation.LIST_CANDIDATES)
    assert isinstance(adapter.probe('https://news.example/'), ProbeResult)


@pytest.mark.parametrize('kwargs', [
    {'operation': 'list_candidates', 'adapter_id': 'a', 'adapter_version': '1', 'reason': 'R'},
    {'operation': AdapterOperation.PROBE, 'adapter_id': '', 'adapter_version': '1', 'reason': 'R'},
    {'operation': AdapterOperation.PROBE, 'adapter_id': 'a', 'adapter_version': '1', 'reason': ' '},
])
def test_capability_unavailable_requires_operation_and_reason(kwargs):
    with pytest.raises(ValueError):
        CapabilityUnavailable(**kwargs)


def test_descriptor_validates_operations_and_checkpoint_version():
    with pytest.raises(ValueError):
        AdapterDescriptor('a', '1', frozenset({AdapterOperation.RESUME_FROM_CHECKPOINT}))
    with pytest.raises(ValueError):
        AdapterDescriptor('a', '1', frozenset({'probe'}))
    descriptor = AdapterDescriptor('a', '1', frozenset({AdapterOperation.RESUME_FROM_CHECKPOINT}), 'cp-v1')
    assert descriptor.supports(AdapterOperation.RESUME_FROM_CHECKPOINT)


def test_missing_policy_is_input_not_ready_without_io():
    fetcher, transport, resolver = make_fetcher({})
    result = fetcher.fetch('https://news.example/', None, correlation_id='corr-1')
    assert problem_code(result) == INPUT_NOT_READY
    assert result.values['retryable'] is False and result.values['correlation_id'] == 'corr-1'
    assert transport.requests == [] and resolver.calls == []


@pytest.mark.parametrize('overrides', [
    {'revision': ''}, {'max_redirects': -1}, {'max_redirects': True}, {'max_body_bytes': 0},
    {'allowed_media_types': frozenset()}, {'allowed_media_types': frozenset({'Text/HTML'})},
    {'allowed_media_types': {'text/html'}}, {'timeout_seconds': 0}, {'timeout_seconds': float('inf')},
    {'timeout_seconds': True},
])
def test_fetch_policy_rejects_invalid_limits(overrides):
    with pytest.raises(ValueError):
        make_policy(**overrides)


def test_success_pins_validated_addresses_and_records_safe_observation():
    fetcher, transport, resolver = make_fetcher({'https://news.example/feed': html()})
    result = fetch(fetcher, 'HTTPS://News.Example:443/feed#top')
    assert isinstance(result, FetchedDocument)
    assert result.body == b'<html>ok</html>'
    observation = result.observation
    assert observation.redirect_chain == ('https://news.example/feed',)
    assert (observation.requested_locator, observation.final_locator) == ('https://news.example/feed',) * 2
    assert (observation.status, observation.media_type, observation.size_bytes) == (200, 'text/html', 15)
    assert observation.policy_revision == 'fetch-policy-r1'
    assert transport.requests[0].host == 'news.example'
    assert transport.requests[0].addresses == (ipaddress.ip_address(PUBLIC),)
    assert resolver.calls == ['news.example']


def test_unsafe_initial_locator_never_reaches_transport():
    fetcher, transport, _ = make_fetcher({})
    result = fetch(fetcher, 'http://0x7f000001/')
    assert problem_code(result) == 'UNSAFE_LOCATOR' and result.values['reason'] == 'LOOPBACK_ADDRESS'
    assert transport.requests == []


def test_resolution_failure_is_retryable_problem():
    fetcher, transport, _ = make_fetcher({}, table={})
    result = fetch(fetcher)
    assert problem_code(result) == 'RESOLUTION_FAILED' and result.values['retryable'] is True
    assert transport.requests == []


@pytest.mark.parametrize(('location', 'reason'), [
    ('http://127.0.0.1/admin', 'LOOPBACK_ADDRESS'),
    ('http://2130706433/', 'LOOPBACK_ADDRESS'),
    ('http://169.254.169.254/latest/meta-data/', 'METADATA_ADDRESS'),
    ('http://[::ffff:127.0.0.1]/', 'IPV4_MAPPED_ADDRESS'),
    ('http://localhost:8080/', 'LOCALHOST_NAME'),
    ('file:///etc/passwd', 'UNSUPPORTED_SCHEME'),
])
def test_redirect_to_unsafe_destination_is_not_followed(location, reason):
    fetcher, transport, _ = make_fetcher({'https://news.example/': redirect(location)})
    result = fetch(fetcher)
    assert problem_code(result) == 'UNSAFE_REDIRECT'
    assert (result.values['reason'], result.values['retryable']) == (reason, False)
    assert [request.locator for request in transport.requests] == ['https://news.example/']


def test_redirect_host_is_resolved_and_validated_at_every_hop():
    table = {'news.example': [PUBLIC], 'cdn.example': ['10.0.0.7']}
    fetcher, transport, resolver = make_fetcher({'https://news.example/': redirect('https://cdn.example/a')}, table)
    result = fetch(fetcher)
    assert problem_code(result) == 'UNSAFE_REDIRECT' and result.values['reason'] == 'PRIVATE_ADDRESS'
    assert resolver.calls == ['news.example', 'cdn.example']
    assert len(transport.requests) == 1


def test_safe_relative_redirect_is_followed_and_chain_recorded():
    routes = {'https://news.example/old': redirect('/new?id=1', 301), 'https://news.example/new?id=1': html()}
    fetcher, _, resolver = make_fetcher(routes)
    result = fetch(fetcher, 'https://news.example/old')
    assert isinstance(result, FetchedDocument)
    assert result.observation.redirect_chain == ('https://news.example/old', 'https://news.example/new?id=1')
    assert result.observation.final_locator == 'https://news.example/new?id=1'
    assert resolver.calls == ['news.example', 'news.example']
    assert routes['https://news.example/old'].body.closed


def test_redirect_loop_is_detected():
    routes = {
        'https://news.example/a': redirect('/b'),
        'https://news.example/b': redirect('https://NEWS.example/a#x'),
    }
    fetcher, transport, _ = make_fetcher(routes)
    assert problem_code(fetch(fetcher, 'https://news.example/a', max_redirects=10)) == 'REDIRECT_LOOP'
    assert len(transport.requests) == 2


def chain_routes():
    return {
        'https://news.example/1': redirect('/2'),
        'https://news.example/2': redirect('/3'),
        'https://news.example/3': html(),
    }


def test_redirect_limit_comes_from_policy():
    fetcher, transport, _ = make_fetcher(chain_routes())
    assert problem_code(fetch(fetcher, 'https://news.example/1', max_redirects=1)) == 'TOO_MANY_REDIRECTS'
    assert len(transport.requests) == 2
    fetcher, _, _ = make_fetcher(chain_routes())
    result = fetch(fetcher, 'https://news.example/1', max_redirects=2)
    assert isinstance(result, FetchedDocument) and len(result.observation.redirect_chain) == 3


def test_redirect_without_location_is_problem():
    fetcher, _, _ = make_fetcher({'https://news.example/': response(302)})
    assert problem_code(fetch(fetcher)) == 'REDIRECT_WITHOUT_LOCATION'


def test_oversized_body_stops_reading_at_policy_limit():
    big = response(200, (('Content-Type', 'text/html'),), [b'x' * 100] * 10)
    fetcher, _, _ = make_fetcher({'https://news.example/': big})
    assert problem_code(fetch(fetcher, max_body_bytes=250)) == 'BODY_TOO_LARGE'
    assert big.body.consumed == 3
    assert big.body.closed


def test_declared_length_over_limit_is_rejected_before_reading():
    big = response(200, (('Content-Type', 'text/html'), ('Content-Length', '5000')), [b'x'])
    fetcher, _, _ = make_fetcher({'https://news.example/': big})
    assert problem_code(fetch(fetcher)) == 'BODY_TOO_LARGE'
    assert big.body.consumed == 0


@pytest.mark.parametrize('headers', [(('Content-Type', 'application/octet-stream'),), ()])
def test_media_type_outside_policy_is_rejected_without_reading(headers):
    resp = response(200, headers, [b'MZ'])
    fetcher, _, _ = make_fetcher({'https://news.example/': resp})
    assert problem_code(fetch(fetcher)) == 'MEDIA_TYPE_NOT_ALLOWED'
    assert resp.body.consumed == 0


def test_transport_timeout_maps_to_retryable_problem():
    fetcher, _, _ = make_fetcher({'https://news.example/': TimeoutError('fake timeout')})
    result = fetch(fetcher)
    assert problem_code(result) == 'FETCH_TIMEOUT' and result.values['retryable'] is True


def test_connection_error_maps_to_retryable_problem():
    fetcher, _, _ = make_fetcher({'https://news.example/': ConnectionRefusedError('fake refused')})
    result = fetch(fetcher)
    assert problem_code(result) == 'CONNECTION_FAILED' and result.values['retryable'] is True


def test_policy_deadline_bounds_body_read():
    slow = response(200, (('Content-Type', 'text/html'),), [b'a', b'b', b'c'])
    fetcher, transport, _ = make_fetcher({'https://news.example/': slow}, clock=FakeClock(step=4.0))
    result = fetch(fetcher, timeout_seconds=10.0)
    assert problem_code(result) == 'FETCH_TIMEOUT' and result.values['retryable'] is True
    assert 0 < transport.requests[0].timeout_seconds <= 10.0
    assert slow.body.consumed < 3


def test_redirect_hops_share_one_deadline():
    routes = {'https://news.example/': redirect('/next'), 'https://news.example/next': html()}
    fetcher, transport, _ = make_fetcher(routes, clock=FakeClock(step=6.0))
    assert problem_code(fetch(fetcher, timeout_seconds=10.0)) == 'FETCH_TIMEOUT'
    assert len(transport.requests) == 1


@pytest.mark.parametrize(('value', 'expected'), [
    ('120', 120), ('Mon, 19 Oct 2026 12:01:30 GMT', 90), (None, None), ('soon', None),
])
def test_rate_limit_maps_retry_after_to_retryable_problem(value, expected):
    headers = () if value is None else (('Retry-After', value),)
    fetcher, _, _ = make_fetcher({'https://news.example/': response(429, headers)})
    result = fetch(fetcher)
    assert problem_code(result) == 'RATE_LIMITED'
    assert (result.values['retryable'], result.values['status']) == (True, 429)
    assert result.values['retry_after_seconds'] == expected


@pytest.mark.parametrize(('value', 'expected'), [
    ('0', 0), (' 30 ', 30), ('-5', None), ('1.5', None), ('', None), (None, None),
    ('Mon, 19 Oct 2026 11:00:00 GMT', 0),
])
def test_parse_retry_after(value, expected):
    assert parse_retry_after(value, NOW) == expected


@pytest.mark.parametrize(('status', 'expected', 'retryable'), [
    (503, 'UPSTREAM_ERROR', True), (408, 'UPSTREAM_ERROR', True),
    (404, 'HTTP_STATUS_REJECTED', False), (304, 'HTTP_STATUS_REJECTED', False),
])
def test_http_status_problems(status, expected, retryable):
    fetcher, _, _ = make_fetcher({'https://news.example/': response(status)})
    result = fetch(fetcher)
    assert problem_code(result) == expected
    assert (result.values['retryable'], result.values['status']) == (retryable, status)


def test_safe_headers_drop_credentials_cookies_and_tokens():
    headers = (
        ('Authorization', 'x'), ('COOKIE', 'x'), ('set-cookie', 'x'), ('X-Auth-Token', 'x'),
        ('X-CSRF-Token', 'x'), ('Content-Type', 'text/html'), ('ETag', '"1"'),
    )
    assert safe_headers(headers) == (('content-type', 'text/html'), ('etag', '"1"'))


def test_sensitive_headers_never_reach_observation_or_log(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    extra = (
        ('Authorization', f'Bearer {SECRET}'), ('Proxy-Authorization', SECRET), ('Set-Cookie', f'sid={SECRET}'),
        ('Cookie', f'a={SECRET}'), ('X-Api-Token', SECRET), ('X-Request-Id', 'req-1'),
    )
    fetcher, _, _ = make_fetcher({'https://news.example/': html(extra=extra)})
    result = fetch(fetcher)
    assert isinstance(result, FetchedDocument)
    assert [name for name, _ in result.observation.safe_headers] == ['content-type', 'x-request-id']
    assert SECRET not in repr(result)
    assert 'secure fetch hop=1 status=200' in caplog.text
    assert SECRET not in caplog.text


def test_problem_and_log_do_not_echo_credentials(caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    headers = (('Set-Cookie', f'sid={SECRET}'), ('Authorization', SECRET), ('Retry-After', '5'))
    fetcher, _, _ = make_fetcher({'https://news.example/': response(429, headers)})
    result = fetch(fetcher)
    assert problem_code(result) == 'RATE_LIMITED'
    assert SECRET not in repr(result.values)
    assert 'secure fetch problem code=RATE_LIMITED' in caplog.text
    assert SECRET not in caplog.text
