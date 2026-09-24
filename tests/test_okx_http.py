"""I-b-3 synthetic transport tests. Never contacts OKX or reads credentials."""

import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

from catos import bounded_pagination as pages
from catos import okx_collection as collection
from catos import okx_http as http


class FakeClock:
    def __init__(self, wall=0):
        self.wall = wall
        self.mono = 0

    def wall_ms(self):
        return self.wall

    def monotonic_ms(self):
        return self.mono

    def advance(self, ms):
        self.wall += ms
        self.mono += ms

    def sleep(self, ms):
        self.advance(ms)


class ScriptedSender:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome(request) if callable(outcome) else outcome


def scope(**changes):
    values = dict(account_alias="fixture-sub", environment="demo",
                  instrument="BTC-USDT-SWAP", window_start_ms=100,
                  window_end_ms=200, max_requests=60,
                  max_pages_per_endpoint=40, request_timeout_ms=2_000,
                  max_runtime_ms=30_000)
    values.update(changes)
    return collection.RunScope(**values)


def body(data, *, code="0", status=200, headers=()):
    payload = json.dumps({"code": code, "data": data}, separators=(",", ":")).encode()
    return http.WireResponse(status, tuple(headers), payload)


def transport(sender, *, selected=None, clock=None, known_orders=(), known_algos=(),
              order_id=None, algo_id=None):
    selected = selected or scope()
    clock = clock or FakeClock()
    return http.DemoReadTransport(
        selected, http.HTTPOptions(http.GLOBAL_DEMO_HOST),
        http.MemoryCredentials("key", "secret", "pass"), sender=sender,
        known_order_ids=known_orders, known_algo_ids=known_algos,
        order_id=order_id, algo_id=algo_id, wall_ms=clock.wall_ms,
        monotonic_ms=clock.monotonic_ms, sleep_ms=clock.sleep), clock


def request(alias, selected, *, page=1, cursor=None, timeout=2_000):
    return collection.PageRequest(collection.ENDPOINTS[alias], selected, page, cursor, timeout)


def _write_test_certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, http.GLOBAL_DEMO_HOST)])
    certificate = (x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2040, 1, 1, tzinfo=timezone.utc))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(http.GLOBAL_DEMO_HOST)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256()))
    cert_path = Path(directory, "cert.pem")
    key_path = Path(directory, "key.pem")
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return cert_path, key_path


def _local_tls_send(response_parts, *, timeout_ms=1_000, max_body_bytes=2_000_000,
                    trust_certificate=True):
    """Exercise HTTPSGetSender through verified localhost TLS without external I/O."""
    with tempfile.TemporaryDirectory() as directory:
        cert_path, key_path = _write_test_certificate(directory)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(cert_path, key_path)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        requests = []
        server_errors = []

        def serve():
            try:
                raw, _ = listener.accept()
                with raw, server_context.wrap_socket(raw, server_side=True) as secured:
                    received = bytearray()
                    while b"\r\n\r\n" not in received:
                        chunk = secured.recv(4096)
                        if not chunk:
                            break
                        received.extend(chunk)
                    requests.append(bytes(received))
                    for delay, chunk in response_parts:
                        if delay:
                            time.sleep(delay)
                        try:
                            secured.sendall(chunk)
                        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                            break
            except Exception as exc:
                server_errors.append(exc)
            finally:
                listener.close()

        thread = threading.Thread(target=serve)
        thread.start()
        original_default_context = ssl.create_default_context

        def client_context():
            if trust_certificate:
                return original_default_context(cafile=str(cert_path))
            return original_default_context()

        def local_connect(host, context, deadline):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            raw = socket.create_connection(("127.0.0.1", port), timeout=remaining)
            raw.settimeout(remaining)
            return context.wrap_socket(raw, server_hostname=host)

        wire = http.WireRequest(http.GLOBAL_DEMO_HOST, "/api/v5/public/time",
            (("Accept", "application/json"), ("Accept-Encoding", "identity"),
             ("x-simulated-trading", "1")), timeout_ms, max_body_bytes)
        try:
            with mock.patch.object(http.ssl, "create_default_context", side_effect=client_context), \
                    mock.patch.object(http, "_connect_tls", side_effect=local_connect), \
                    mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:1"}):
                result = http.HTTPSGetSender().send(wire)
        finally:
            thread.join(timeout=2)
        if thread.is_alive():
            raise AssertionError("local TLS server did not finish")
        if server_errors:
            raise server_errors[0]
        return result, requests


class RestrictedTransportTests(unittest.TestCase):
    def test_private_signature_golden_vector_and_public_auth_separation(self):
        sender = ScriptedSender(
            body([{"instId": "BTC-USDT-SWAP", "billId": "B1", "tradeId": "T1", "ordId": "O1"}]),
            body([{"ts": "1"}]))
        t, clock = transport(sender, clock=FakeClock(0))
        t.fetch(request("fills", t.scope))
        t.fetch(request("public_time", t.scope))

        private_headers = dict(sender.requests[0].headers)
        self.assertEqual(sender.requests[0].target,
                         "/api/v5/trade/fills?begin=100&end=200&instId=BTC-USDT-SWAP&instType=SWAP&limit=100")
        self.assertEqual(private_headers["OK-ACCESS-TIMESTAMP"], "1970-01-01T00:00:00.000Z")
        self.assertEqual(private_headers["OK-ACCESS-SIGN"],
                         "o4JFRKrXqJHIdoSC4DQyYPqVcGMifnaHzPLbXoESPSU=")
        self.assertEqual(private_headers["x-simulated-trading"], "1")
        public_headers = dict(sender.requests[1].headers)
        self.assertEqual(public_headers["x-simulated-trading"], "1")
        self.assertFalse(any(name.startswith("OK-ACCESS-") for name in public_headers))
        self.assertEqual(clock.mono, 500)

    def test_real_sender_uses_verified_tls_get_headers_and_ignores_proxy_env(self):
        payload = b'{"code":"0","data":[{"ts":"1"}]}'
        raw = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " +
               str(len(payload)).encode() + b"\r\nConnection: close\r\n\r\n" + payload)
        response, requests = _local_tls_send(((0, raw),))
        self.assertEqual((response.status, response.body), (200, payload))
        self.assertEqual(len(requests), 1)
        first_line, headers = requests[0].split(b"\r\n", 1)
        self.assertEqual(first_line, b"GET /api/v5/public/time HTTP/1.1")
        self.assertIn(b"Host: openapi.okx.com", headers)
        self.assertIn(b"x-simulated-trading: 1", headers)
        self.assertNotIn(b"Cookie:", headers)

    def test_real_sender_rejects_untrusted_tls_certificate(self):
        payload = b'{"code":"0","data":[{"ts":"1"}]}'
        raw = (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(payload)).encode() +
               b"\r\nConnection: close\r\n\r\n" + payload)
        with self.assertRaisesRegex(collection.TransportError, "transport_error"):
            _local_tls_send(((0, raw),), trust_certificate=False)

    def test_real_sender_does_not_follow_redirect_or_read_error_body(self):
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                raw = (f"HTTP/1.1 {status} Redirect\r\n".encode() +
                       b"Location: https://evil.example/\r\nContent-Length: 12\r\n"
                       b"Connection: close\r\n\r\nSECRET-BODY")
                response, requests = _local_tls_send(((0, raw),))
                self.assertEqual((response.status, response.body), (status, b""))
                self.assertEqual(len(requests), 1)
                self.assertNotIn(b"evil.example", requests[0])

    def test_real_sender_enforces_content_and_body_bounds(self):
        cases = (
            (b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\n12345678901",
             10, "body_limit_exceeded"),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nContent-Length: 5\r\nConnection: close\r\n\r\n12345",
             10, "body_limit_exceeded"),
            (b"HTTP/1.1 200 OK\r\nContent-Length: nope\r\nConnection: close\r\n\r\n12345",
             10, "body_limit_exceeded"),
            (b"HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nContent-Length: 1\r\nConnection: close\r\n\r\nx",
             10, "unsupported_content_encoding"),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\n12345",
             10, "truncated_body"),
            (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\nB\r\n12345678901\r\n0\r\n\r\n",
             10, "body_limit_exceeded"),
        )
        for raw, maximum, issue in cases:
            with self.subTest(issue=issue), self.assertRaisesRegex(collection.TransportError, issue):
                _local_tls_send(((0, raw),), max_body_bytes=maximum)

    def test_real_sender_deadline_covers_headers_and_body(self):
        payload = b'{"code":"0","data":[]}'
        header = (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(payload)).encode() +
                  b"\r\nConnection: close\r\n\r\n")
        for parts in ((((0.08, header + payload),)), (((0, header), (0.08, payload)))):
            with self.subTest(parts=len(parts)), self.assertRaisesRegex(collection.TransportError, "timeout"):
                _local_tls_send(parts, timeout_ms=30)

    def test_repr_and_audit_do_not_expose_credentials_ids_or_body(self):
        creds = http.MemoryCredentials("SECRETKEY", "SECRET", "PASSPHRASE")
        self.assertNotIn("SECRET", repr(creds))
        wire = http.WireRequest(http.GLOBAL_DEMO_HOST, "/api/v5/account/balance?ordId=SECRET-ID",
                                (("x-simulated-trading", "1"),), 1, 100)
        self.assertNotIn("SECRET-ID", repr(wire))
        self.assertNotIn("SECRET-BODY", repr(http.WireResponse(200, (), b"SECRET-BODY")))

        sender = ScriptedSender(body([{"instType": "SWAP", "instId": "BTC-USDT-SWAP",
                                       "ordId": "SECRET-ID"}]), body([]))
        t, _ = transport(sender)
        first = t.fetch(request("orders_pending", t.scope))
        t.fetch(request("orders_pending", t.scope, page=2, cursor=first.next_cursor))
        self.assertNotIn("SECRET-ID", json.dumps(t.audit(), sort_keys=True))

    def test_host_path_header_and_demo_header_are_closed(self):
        with self.assertRaises(ValueError):
            http.HTTPOptions("evil.example")
        cases = [
            http.WireRequest("evil.example", "/api/v5/account/balance",
                             (("x-simulated-trading", "1"),), 1, 100),
            http.WireRequest(http.GLOBAL_DEMO_HOST, "/api/v5/account/balance/../trade/order",
                             (("x-simulated-trading", "1"),), 1, 100),
            http.WireRequest(http.GLOBAL_DEMO_HOST, "/api/v5/account/balance",
                             (("x-simulated-trading", "1"), ("X-Evil", "1")), 1, 100),
            http.WireRequest(http.GLOBAL_DEMO_HOST, "/api/v5/account/balance", (), 1, 100),
        ]
        for item in cases:
            with self.subTest(item=repr(item)), self.assertRaises(ValueError):
                http._wire_guard(item)

    def test_query_contract_and_fill_cursor_use_bill_id(self):
        sender = ScriptedSender(
            body([{"instId": "BTC-USDT-SWAP", "billId": "BILL1", "tradeId": "TRADE9", "ordId": "ORD1"}]),
            body([]))
        t, _ = transport(sender)
        first = t.fetch(request("fills", t.scope))
        self.assertIsNotNone(first.next_cursor)  # Short non-empty page must continue.
        self.assertEqual(first.window_evidence, collection.WindowRequestEvidence(100, 200))
        t.fetch(request("fills", t.scope, page=2, cursor=first.next_cursor))

        first_query = dict(parse_qsl(urlsplit(sender.requests[0].target).query))
        self.assertEqual(first_query, {"begin": "100", "end": "200", "instId": "BTC-USDT-SWAP",
                                       "instType": "SWAP", "limit": "100"})
        second_query = dict(parse_qsl(urlsplit(sender.requests[1].target).query))
        self.assertEqual(second_query["after"], "BILL1")
        self.assertNotIn("TRADE9", sender.requests[1].target)

    def test_orders_history_window_evidence_uses_ctime_and_order_cursor(self):
        sender = ScriptedSender(
            body([{"instId": "BTC-USDT-SWAP", "ordId": "ORDER1"}]),
            body([]))
        t, _ = transport(sender)
        first = t.fetch(request("orders_history", t.scope))
        self.assertEqual(
            first.window_evidence,
            collection.WindowRequestEvidence(100, 200, "cTime", "after_order_id"),
        )
        t.fetch(request("orders_history", t.scope, page=2, cursor=first.next_cursor))
        first_query = dict(parse_qsl(urlsplit(sender.requests[0].target).query))
        second_query = dict(parse_qsl(urlsplit(sender.requests[1].target).query))
        self.assertEqual(first_query["begin"], "100")
        self.assertEqual(first_query["end"], "200")
        self.assertEqual(second_query["after"], "ORDER1")

    def test_account_level_query_filters_do_not_hide_responsibility(self):
        sender = ScriptedSender(body([]), body([]), body([]))
        t, _ = transport(sender)
        for alias in ("positions", "orders_pending", "bills"):
            t.fetch(request(alias, t.scope))
        queries = [dict(parse_qsl(urlsplit(item.target).query)) for item in sender.requests]
        self.assertEqual(queries[0], {"instType": "SWAP"})
        self.assertEqual(queries[1], {"instType": "SWAP", "limit": "100"})
        self.assertEqual(queries[2], {"begin": "100", "end": "200", "limit": "100"})
        self.assertNotIn("instId", queries[0])
        self.assertNotIn("instId", queries[1])
        self.assertNotIn("ccy", queries[2])
        self.assertNotIn("instType", queries[2])

    def test_cross_page_duplicate_id_is_rejected(self):
        sender = ScriptedSender(
            body([{"instId": "BTC-USDT-SWAP", "billId": "A", "tradeId": "T1", "ordId": "O1"},
                  {"instId": "BTC-USDT-SWAP", "billId": "B", "tradeId": "T2", "ordId": "O2"}]),
            body([{"instId": "BTC-USDT-SWAP", "billId": "A", "tradeId": "T1", "ordId": "O1"},
                  {"instId": "BTC-USDT-SWAP", "billId": "C", "tradeId": "T3", "ordId": "O3"}]))
        t, _ = transport(sender)
        first = t.fetch(request("fills", t.scope))
        with self.assertRaisesRegex(collection.TransportError, "nonprogressing_page"):
            t.fetch(request("fills", t.scope, page=2, cursor=first.next_cursor))

    def test_algo_pending_and_history_walk_all_partitions(self):
        for alias, count in (("algo_pending", 7), ("algo_history", 21)):
            with self.subTest(alias=alias):
                clock = FakeClock()
                sender = ScriptedSender(*(body([]) for _ in range(count)))
                selected = scope(max_requests=30, max_pages_per_endpoint=30, max_runtime_ms=30_000)
                t, _ = transport(sender, selected=selected, clock=clock)
                result = collection.collect_plan(collection.CollectionPlan(selected, (alias,)), t,
                                                 clock=clock, sleep_ms=clock.sleep)
                self.assertTrue(result.manifest.complete)
                self.assertEqual((result.manifest.requests, t.audit()["wire_attempts"]), (count, count))
                self.assertEqual(len({(a["ord_type"], a["state"]) for a in t.audit()["attempts"]}), count)

    def test_algo_budget_shortage_is_incomplete_without_skipping_partitions(self):
        clock = FakeClock()
        sender = ScriptedSender(body([]), body([]), body([]))
        selected = scope(max_requests=3, max_pages_per_endpoint=30)
        t, _ = transport(sender, selected=selected, clock=clock)
        result = collection.collect_plan(collection.CollectionPlan(selected, ("algo_pending",)), t,
                                         clock=clock, sleep_ms=clock.sleep)
        endpoint = result.manifest.endpoint_manifests[0]
        self.assertFalse(endpoint.complete)
        self.assertEqual(endpoint.issue, "request_budget_exhausted")
        self.assertEqual(t.audit()["wire_attempts"], 3)

    def test_partition_mismatch_is_not_accepted(self):
        sender = ScriptedSender(body([{"instType": "SWAP", "instId": "BTC-USDT-SWAP",
                                       "algoId": "A1", "ordType": "trigger"}]))
        t, _ = transport(sender)
        with self.assertRaisesRegex(collection.TransportError, "partition_mismatch"):
            t.fetch(request("algo_pending", t.scope))

    def test_rate_limit_retry_is_counted_resigned_and_same_page(self):
        clock = FakeClock()
        sender = ScriptedSender(http.WireResponse(429, (("retry-after", "0"),), b""), body([{}]))
        selected = scope(max_requests=3)
        t, _ = transport(sender, selected=selected, clock=clock)
        result = collection.collect_plan(collection.CollectionPlan(selected, ("balance",)), t,
                                         clock=clock, retry_policy=pages.RetryPolicy(1, 500, 1_000),
                                         sleep_ms=clock.sleep)
        self.assertTrue(result.manifest.complete)
        self.assertEqual(result.manifest.requests, 2)
        self.assertEqual(t.audit()["wire_attempts"], 2)
        first, second = (dict(item.headers) for item in sender.requests)
        self.assertNotEqual(first["OK-ACCESS-TIMESTAMP"], second["OK-ACCESS-TIMESTAMP"])
        self.assertEqual([a["page_number"] for a in t.audit()["attempts"]], [1, 1])

    def test_api_50011_retries_and_batch_request_budget_does_not_reset(self):
        clock = FakeClock()
        sender = ScriptedSender(body([], code="50011", headers=(("retry-after", "0"),)), body([{}]))
        selected = scope(max_requests=2)
        t, _ = transport(sender, selected=selected, clock=clock)
        result = collection.collect_plan(collection.CollectionPlan(selected, ("balance", "public_time")), t,
                                         clock=clock, retry_policy=pages.RetryPolicy(1, 500, 1_000),
                                         sleep_ms=clock.sleep)
        self.assertFalse(result.manifest.complete)
        self.assertEqual(result.manifest.requests, 2)
        self.assertEqual(t.audit()["wire_attempts"], 2)
        self.assertTrue(result.manifest.endpoint_manifests[0].complete)
        self.assertEqual(result.manifest.endpoint_manifests[1].issue,
                         "not_started:request_budget_exhausted")

    def test_transport_runtime_budget_is_shared_across_sources(self):
        clock = FakeClock()
        sender = ScriptedSender(body([{}]))
        selected = scope(max_runtime_ms=500)
        t, _ = transport(sender, selected=selected, clock=clock)
        result = collection.collect_plan(collection.CollectionPlan(selected, ("balance", "public_time")), t,
                                         clock=clock, sleep_ms=clock.sleep)
        self.assertFalse(result.manifest.complete)
        self.assertTrue(result.manifest.endpoint_manifests[0].complete)
        self.assertEqual(result.manifest.endpoint_manifests[1].issue, "timeout")
        self.assertEqual(t.audit()["wire_attempts"], 1)

    def test_retry_after_date_and_over_cap_are_conservative(self):
        self.assertEqual(http._retry_after((("Retry-After", "Thu, 01 Jan 1970 00:00:02 GMT"),), 0), 2_000)
        invalid = (
            (("Retry-After", "1"), ("Retry-After", "2")),
            (("Retry-After", "x" * 129),),
            (("Retry-After", "not-a-date"),),
        )
        for headers in invalid:
            with self.subTest(headers=headers), self.assertRaisesRegex(collection.TransportError, "invalid_retry_after"):
                http._retry_after(headers, 0)

        clock = FakeClock()
        sender = ScriptedSender(http.WireResponse(429, (("retry-after", "2"),), b""))
        selected = scope(max_requests=3)
        t, _ = transport(sender, selected=selected, clock=clock)
        result = collection.collect_plan(collection.CollectionPlan(selected, ("balance",)), t,
                                         clock=clock, retry_policy=pages.RetryPolicy(2, 500, 1_000),
                                         sleep_ms=clock.sleep)
        self.assertEqual(result.manifest.endpoint_manifests[0].issue, "rate_limited")
        self.assertEqual(t.audit()["wire_attempts"], 1)

    def test_timeout_and_sender_exception_are_not_retried_or_leaked(self):
        for error, expected in ((collection.TransportError("timeout"), "timeout"),
                                (RuntimeError("SECRET-BODY"), "malformed_response")):
            with self.subTest(expected=expected):
                clock = FakeClock()
                sender = ScriptedSender(error)
                selected = scope(max_requests=3)
                t, _ = transport(sender, selected=selected, clock=clock)
                result = collection.collect_plan(collection.CollectionPlan(selected, ("balance",)), t,
                                                 clock=clock, retry_policy=pages.RetryPolicy(2, 500, 1_000),
                                                 sleep_ms=clock.sleep)
                self.assertEqual(result.manifest.endpoint_manifests[0].issue, expected)
                self.assertEqual(t.audit()["wire_attempts"], 1)
                self.assertNotIn("SECRET-BODY", repr(result) + json.dumps(t.audit()))

    def test_unknown_detail_id_rejected_before_sender(self):
        sender = ScriptedSender(body([]))
        t, _ = transport(sender, known_orders=("KNOWN",), order_id="UNKNOWN")
        with self.assertRaisesRegex(collection.TransportError, "detail_id_not_authorized"):
            t.fetch(request("order", t.scope))
        self.assertEqual(sender.requests, [])

    def test_observed_target_id_can_be_selected_but_foreign_id_cannot(self):
        sender = ScriptedSender(body([
            {"instType": "SWAP", "instId": "BTC-USDT-SWAP", "ordId": "TARGET"},
            {"instType": "SWAP", "instId": "ETH-USDT-SWAP", "ordId": "FOREIGN"},
        ]))
        t, _ = transport(sender)
        t.fetch(request("orders_pending", t.scope))
        t.select_detail("order", "TARGET")
        with self.assertRaises(ValueError):
            t.select_detail("order", "FOREIGN")

    def test_detail_query_and_response_identity_are_bound(self):
        sender = ScriptedSender(body([{"instType": "SWAP", "instId": "BTC-USDT-SWAP", "ordId": "OTHER"}]))
        t, _ = transport(sender, known_orders=("KNOWN",), order_id="KNOWN")
        with self.assertRaisesRegex(collection.TransportError, "detail_identity_mismatch"):
            t.fetch(request("order", t.scope))
        query = dict(parse_qsl(urlsplit(sender.requests[0].target).query))
        self.assertEqual(query, {"instId": "BTC-USDT-SWAP", "ordId": "KNOWN"})
        self.assertNotIn("instType", query)

    def test_json_parser_rejects_duplicate_keys_float_nan_utf8_and_depth(self):
        bad = [
            b'{"code":"0","code":"0","data":[]}',
            b'{"code":"0","data":[1.5]}',
            b'{"code":"0","data":[NaN]}',
            b'\xff',
        ]
        deep = {"code": "0", "data": []}
        cursor = deep["data"]
        for _ in range(40):
            child = []
            cursor.append(child)
            cursor = child
        bad.append(json.dumps(deep).encode())
        for raw in bad:
            with self.subTest(raw=raw[:20]), self.assertRaisesRegex(collection.TransportError, "malformed_response"):
                http._json_body(raw, 2_000_000)

    def test_source_ms_is_local_receive_time(self):
        clock = FakeClock(1000)
        def respond(_request):
            clock.advance(7)
            return body([{}])
        sender = ScriptedSender(respond)
        t, _ = transport(sender, clock=clock)
        response = t.fetch(request("balance", t.scope))
        self.assertEqual(response.source_ms, 1007)


if __name__ == "__main__":
    unittest.main()
