"""Real HTTP(S) transport for SecureFetcher (ADAPT-A; A-RULE-013, A-RULE-014).

Sends one GET per hop with http.client and connects only to the pinned addresses of the
TransportRequest. It never follows a redirect, never reads proxy settings or ambient
process variables, and returns the body as a chunk iterator so SecureFetcher keeps the size and time limits.
"""
from __future__ import annotations

import http.client
import logging
import socket
import ssl
from collections.abc import Iterator
from urllib.parse import urlsplit

from source_ingestion.adapters.secure_fetch import TransportRequest, TransportResponse
from source_ingestion.domain.locator import IPAddress

_LOG = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 65536
DEFAULT_USER_AGENT = 'AutoVideoCreator-SourceIngestion/1.0'
_DEFAULT_PORTS = {'http': 80, 'https': 443}


def _connect_pinned(addresses: tuple[IPAddress, ...], port: int, timeout: float) -> socket.socket:
    """TCP connection to the first reachable pinned address; no name resolution happens here."""
    last_error: OSError = ConnectionError('NO_PINNED_ADDRESS')
    for address in addresses:
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            sock.connect((str(address), port))
        except OSError as error:
            sock.close()
            last_error = error
            continue
        return sock
    raise last_error


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, addresses: tuple[IPAddress, ...], timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._pinned = addresses

    def connect(self) -> None:
        self.sock = _connect_pinned(self._pinned, self.port, self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TCP to the pinned address; TLS uses SNI and certificate verification against `host`."""

    def __init__(self, host: str, port: int, addresses: tuple[IPAddress, ...], timeout: float) -> None:
        self._tls_context = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._tls_context)
        self._pinned = addresses

    def connect(self) -> None:
        sock = _connect_pinned(self._pinned, self.port, self.timeout)
        try:
            self.sock = self._tls_context.wrap_socket(sock, server_hostname=self.host)
        except OSError:
            sock.close()
            raise


class _ResponseBody:
    """Chunk iterator over one response; close() releases the connection even before iteration starts."""

    def __init__(
        self, connection: http.client.HTTPConnection, response: http.client.HTTPResponse, chunk_size: int
    ) -> None:
        self._connection = connection
        self._response = response
        self._chunk_size = chunk_size

    def __iter__(self) -> Iterator[bytes]:
        while True:
            try:
                chunk = self._response.read(self._chunk_size)
            except http.client.HTTPException:
                raise ConnectionError('HTTP_BODY_READ_FAILED') from None
            if not chunk:
                return
            yield chunk

    def close(self) -> None:
        self._response.close()
        self._connection.close()


class RealHttpTransport:
    """Transport for SecureFetcher: GET only, pinned addresses, no redirect, no proxy, chunked body."""

    def __init__(self, *, user_agent: str = DEFAULT_USER_AGENT, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError('INVALID_TRANSPORT_CONFIG')
        if type(chunk_size) is not int or chunk_size <= 0:
            raise ValueError('INVALID_TRANSPORT_CONFIG')
        self._user_agent = user_agent.strip()
        self._chunk_size = chunk_size

    def send(self, request: TransportRequest) -> TransportResponse:
        parts = urlsplit(request.locator)
        scheme = parts.scheme.lower()
        if scheme not in _DEFAULT_PORTS:
            raise ConnectionError('UNSUPPORTED_SCHEME')
        port = parts.port or _DEFAULT_PORTS[scheme]
        target = (parts.path or '/') + ('?' + parts.query if parts.query else '')
        connection_class = _PinnedHTTPSConnection if scheme == 'https' else _PinnedHTTPConnection
        connection = connection_class(request.host, port, request.addresses, request.timeout_seconds)
        headers = {
            'User-Agent': self._user_agent,
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'close',
        }
        try:
            connection.request('GET', target, headers=headers)
            response = connection.getresponse()
        except http.client.HTTPException:
            connection.close()
            raise ConnectionError('HTTP_PROTOCOL_ERROR') from None
        except BaseException:
            connection.close()
            raise
        _LOG.debug('real transport status=%d', response.status)
        body = _ResponseBody(connection, response, self._chunk_size)
        return TransportResponse(response.status, tuple(response.getheaders()), body)
