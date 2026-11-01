"""Bounded unauthenticated HTTPS image reads, no proxies, cookies or redirects.

Resolve once, reject every non-global address, connect to that exact IP while
retaining original TLS SNI/certificate hostname verification. No browser buffers.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit
from parsing import image_url_safe

class MediaAccessBlocked(RuntimeError):
    pass

class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout=15):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address
    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise

def open_response(url, socket_timeout=15):
    safe = image_url_safe(url)
    if safe is None or safe != url or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise RuntimeError('UNSAFE_IMAGE_URL')
    parsed = urlsplit(safe)
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    ips = [a[4][0] for a in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise RuntimeError('NON_PUBLIC_IMAGE_DNS')
    conn = PinnedHTTPSConnection(parsed.hostname, ips[0], timeout=socket_timeout)
    try:
        conn.request('GET', parsed.path or '/', headers={
            'Accept-Encoding':'identity', 'User-Agent':'AromatnyOwnStoreReadOnly/1.0',
            'Accept':'image/jpeg,image/png,image/webp', 'Connection':'close'})
        return conn, conn.getresponse()
    except BaseException:
        conn.close()
        raise

def fetch_image(url, max_bytes, *, socket_timeout=15, total_timeout=45):
    # Explicit bounded budgets for slow connections; conservative CLI defaults
    # and all source/DNS/TLS/status/byte checks remain identical.
    if (type(socket_timeout) is not int or not 1 <= socket_timeout <= 120 or
            type(total_timeout) is not int or not socket_timeout <= total_timeout <= 360):
        raise ValueError('INVALID_IMAGE_TIME_BUDGET')
    started = time.monotonic()
    conn, response = open_response(url, socket_timeout=socket_timeout)
    try:
        if response.status in (401,403,429):
            raise MediaAccessBlocked(f'Image CDN refused access: {response.status}; stop')
        if response.status != 200:
            raise RuntimeError(f'IMAGE_STATUS_{response.status}_NO_REDIRECTS')
        encoding = response.getheader('Content-Encoding')
        if encoding and encoding.lower() != 'identity':
            raise RuntimeError('COMPRESSED_HTTP_IMAGE_FORBIDDEN')
        length = response.getheader('Content-Length')
        if length is not None and not (64 <= int(length) <= max_bytes):
            raise RuntimeError('IMAGE_SIZE_OUT_OF_RANGE')
        data = bytearray()
        while True:
            if time.monotonic() - started > total_timeout:
                raise RuntimeError('IMAGE_TOTAL_TIME_BUDGET_EXCEEDED')
            # read(n) may assemble n bytes indefinitely under slow trickle traffic.
            # read1 performs at most one underlying buffered read, so the total-time
            # check regains control between socket reads (socket timeout still applies).
            chunk = response.read1(min(64*1024, max_bytes+1-len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                raise RuntimeError('IMAGE_TOO_LARGE')
        if len(data) < 64 or (length is not None and len(data) != int(length)):
            raise RuntimeError('TRUNCATED_OR_EMPTY_IMAGE')
        return bytes(data)
    finally:
        response.close()
        conn.close()
