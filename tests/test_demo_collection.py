"""I-b-4 synthetic runner tests. Never reads the authorized file or contacts OKX."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from catos import demo_collection as demo
from catos import okx_collection as collection
from catos import okx_http as http


class FakeClock:
    def __init__(self, wall=2_000_000_000_000):
        self.wall = wall
        self.mono = 0

    def wall_ms(self):
        return self.wall

    def monotonic_ms(self):
        return self.mono

    def sleep(self, ms):
        self.wall += ms
        self.mono += ms


def wire_body(data, *, code="0", status=200, headers=()):
    payload = json.dumps({"code": code, "data": data}, separators=(",", ":")).encode()
    return http.WireResponse(status, tuple(headers), payload)


def valid_config(**changes):
    row = {
        "uid": "private-main-uid",
        "mainUid": "private-main-uid",
        "acctLv": "2",
        "posMode": "net_mode",
        "roleType": "0",
        "perm": "read_only,trade",
    }
    row.update(changes)
    return row


class SyntheticSender:
    def __init__(self, clock, *, config=None, config_status=200, rate_limits=0):
        self.clock = clock
        self.config = config or valid_config()
        self.config_status = config_status
        self.rate_limits = rate_limits
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        path = request.target.split("?", 1)[0]
        if path == "/api/v5/account/config":
            if self.rate_limits:
                self.rate_limits -= 1
                return http.WireResponse(429, (), b"")
            if self.config_status != 200:
                return http.WireResponse(self.config_status, (), b"")
            return wire_body([self.config])
        if path == "/api/v5/public/time":
            return wire_body([{"ts": str(self.clock.wall_ms())}])
        if path in ("/api/v5/account/instruments", "/api/v5/public/instruments"):
            return wire_body([{
                "instType": "SWAP", "instId": "BTC-USDT-SWAP", "ctType": "linear",
                "settleCcy": "USDT", "ctValCcy": "BTC", "state": "live",
                "ctVal": "0.01", "ctMult": "1", "tickSz": "0.1",
                "lotSz": "0.01", "minSz": "0.01",
            }])
        if path == "/api/v5/account/balance":
            now = str(self.clock.wall_ms())
            return wire_body([{
                "totalEq": "98765.4321", "adjEq": "98765.4321", "uTime": now,
                "details": [{"ccy": "USDT", "uTime": now, "eq": "98765.4321",
                             "liab": "0", "availEq": "98765.4321", "ordFrozen": "0"}],
            }])
        if path == "/api/v5/public/mark-price":
            return wire_body([{"instType": "SWAP", "instId": "BTC-USDT-SWAP",
                               "markPx": "12345.67", "ts": str(self.clock.wall_ms())}])
        return wire_body([])


class FakePageTransport:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        return self.response


def page_request(alias="account_config"):
    scope = demo.authorized_scope(2_000_000_000_000)
    return collection.PageRequest(collection.ENDPOINTS[alias], scope, 1, None, 10_000)


def config_response(row):
    req = page_request()
    return collection.PageResponse(req.scope.account_alias, req.scope.environment,
                                   req.scope.window_end_ms, {"code": "0", "data": [row]})


class CredentialTests(unittest.TestCase):
    def test_subtypes_fixed_signed_demo_get_and_safe_catalog(self):
        clock = FakeClock()
        sender = mock.Mock()
        sender.send.return_value = wire_body([{"type": "1", "typeDesc": "Transfer",
            "subTypeDetails": [{"subType": "11", "subTypeDesc": "Transfer in"}],
            "private_extra": "must-not-export"}])
        result = demo.read_subtypes_once(http.MemoryCredentials("key", "secret", "pass"),
                                        sender=sender, clock=clock)
        request = sender.send.call_args.args[0]
        self.assertEqual(request.target, "/api/v5/account/subtypes")
        self.assertEqual(dict(request.headers)["x-simulated-trading"], "1")
        self.assertIn("OK-ACCESS-SIGN", dict(request.headers))
        self.assertNotIn("must-not-export", json.dumps(result))
        self.assertFalse(result["trade_authorized"])
        self.assertEqual(result["audit"]["wire_attempts"], 1)

    def test_subtypes_empty_duplicate_and_malformed_fail_closed(self):
        row = {"type": "1", "typeDesc": "Transfer", "subTypeDetails": []}
        for data in ([], [row, row], [{"type": "1"}]):
            sender = mock.Mock()
            sender.send.return_value = wire_body(data)
            with self.assertRaisesRegex(demo.SetupError, "subtypes_catalog_invalid"):
                demo.read_subtypes_once(http.MemoryCredentials("key", "secret", "pass"),
                                        sender=sender, clock=FakeClock())

    def test_parse_supported_formats(self):
        cases = (
            '{"api_key":"key","secret":"secret","passphrase":"pass"}',
            "API KEY = key\nsecret_key: secret\napi_passphrase = pass",
            "okx_api_key: key\nokx_api_secret: secret\nokx_passphrase: pass",
            'default_profile="demo1"\n[profiles.demo1]\napi_key=key\nsecret_key=secret\n'
            'passphrase=pass\ndemo=true\n[profiles.demo2]\napi_key=other\n'
            'secret_key=other-secret\npassphrase=other-pass\ndemo=true',
        )
        for raw in cases:
            with self.subTest(raw=raw.splitlines()[0]):
                parsed = demo.parse_credentials(raw)
                self.assertEqual((parsed.api_key, parsed.secret, parsed.passphrase),
                                 ("key", "secret", "pass"))

    def test_parse_rejects_ambiguous_or_incomplete_input_with_fixed_error(self):
        cases = (
            "key\nsecret\npass",
            "api_key=key\nsecret=secret",
            "api_key=key\napikey=other\nsecret=secret\npassphrase=pass",
            "api_key=key\nsecret=secret\npassphrase=pass\naccount=demo",
            'default_profile="missing"\n[profiles.demo1]\napi_key=key\nsecret_key=secret\n'
            'passphrase=pass\ndemo=true',
            'default_profile="demo1"\n[profiles.demo1]\napi_key=key\nsecret_key=secret\n'
            'passphrase=pass\ndemo=false',
        )
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaisesRegex(
                    demo.SetupError, "^credential_format_unsupported$"):
                demo.parse_credentials(raw)

    def test_loader_uses_only_patched_designated_file_and_bounded_encodings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "credential.txt")
            for encoding in ("utf-8-sig", "utf-16"):
                path.write_text("api_key=key\nsecret=secret\npassphrase=pass", encoding=encoding)
                with mock.patch.object(demo, "AUTHORIZED_CREDENTIAL_FILE", path):
                    parsed = demo.load_authorized_credentials()
                self.assertEqual(parsed.api_key, "key")
            path.write_bytes(b"x" * (demo.MAX_CREDENTIAL_BYTES + 1))
            with mock.patch.object(demo, "AUTHORIZED_CREDENTIAL_FILE", path), \
                    self.assertRaisesRegex(demo.SetupError, "^credential_file_size_invalid$"):
                demo.load_authorized_credentials()


class ConfigGateTests(unittest.TestCase):
    def test_valid_config_passes(self):
        transport = FakePageTransport(config_response(valid_config()))
        gate = demo._ConfigGate(transport)
        gate.fetch(page_request())
        self.assertTrue(gate.passed)
        self.assertEqual(gate.issues, set())

    def test_rejected_config_blocks_all_later_transport_calls(self):
        variants = (
            (valid_config(uid="private-sub-uid"), "config_not_main_account"),
            (valid_config(posMode="long_short_mode"), "config_mode_mismatch"),
            (valid_config(acctLv="1"), "config_mode_mismatch"),
            (valid_config(perm="trade"), "config_permission_mismatch"),
            (valid_config(perm="read_only,withdraw"), "config_permission_mismatch"),
            (valid_config(roleType="9"), "config_role_unknown"),
        )
        for row, issue in variants:
            with self.subTest(issue=issue, row=row):
                transport = FakePageTransport(config_response(row))
                gate = demo._ConfigGate(transport)
                gate.fetch(page_request())
                self.assertFalse(gate.passed)
                self.assertIn(issue, gate.issues)
                with self.assertRaises(collection.CollectionInterrupted):
                    gate.fetch(page_request("public_time"))
                self.assertEqual(len(transport.requests), 1)


class RunnerTests(unittest.TestCase):
    def test_fixed_scope_and_endpoint_order(self):
        scope = demo.authorized_scope(2_000_000_000_000)
        self.assertEqual(scope.account_alias, "okx-demo")
        self.assertEqual(scope.environment, "demo")
        self.assertEqual(scope.instrument, "BTC-USDT-SWAP")
        self.assertEqual(scope.window_end_ms - scope.window_start_ms, 86_400_000)
        self.assertEqual((scope.max_requests, scope.max_pages_per_endpoint,
                          scope.request_timeout_ms, scope.max_runtime_ms),
                         (120, 40, 10_000, 180_000))
        self.assertEqual(demo.ENDPOINT_ALIASES[0], "account_config")
        self.assertEqual(demo.ENDPOINT_ALIASES[-1], "algo_history")

    def test_config_mode_read_is_one_demo_request_and_exposes_only_mode(self):
        clock = FakeClock()
        sender = SyntheticSender(clock, config=valid_config(acctLv="1", posMode="long_short_mode"))
        credentials = http.MemoryCredentials("credential-key", "credential-secret", "credential-pass")
        result = demo.read_config_mode_once(credentials, sender=sender, clock=clock,
                                            sleep_ms=clock.sleep)
        self.assertEqual(result, {"acctLv": "1", "posMode": "long_short_mode"})
        self.assertEqual(len(sender.requests), 1)
        request = sender.requests[0]
        # GET is fixed by the sender and checked at the wire boundary in
        # test_okx_http; WireRequest has no configurable method field.
        self.assertIsInstance(request, http.WireRequest)
        self.assertEqual(request.host, http.GLOBAL_DEMO_HOST)
        self.assertEqual(request.target, "/api/v5/account/config")
        self.assertEqual(dict(request.headers)["x-simulated-trading"], "1")
        rendered = json.dumps(result, sort_keys=True)
        for private in ("credential-key", "credential-secret", "credential-pass",
                        "private-main-uid"):
            self.assertNotIn(private, rendered)

    def test_config_mode_read_rejects_subaccount_without_second_request(self):
        clock = FakeClock()
        sender = SyntheticSender(clock, config=valid_config(uid="private-sub-uid"))
        with self.assertRaisesRegex(demo.SetupError, "^config_not_main_account$"):
            demo.read_config_mode_once(http.MemoryCredentials("k", "s", "p"), sender=sender,
                                       clock=clock, sleep_ms=clock.sleep)
        self.assertEqual(len(sender.requests), 1)

    def test_run_once_is_bounded_demo_get_collection_and_summary_is_redacted(self):
        clock = FakeClock()
        sender = SyntheticSender(clock)
        credentials = http.MemoryCredentials("credential-key", "credential-secret", "credential-pass")
        outcome = demo.run_once(credentials, sender=sender, clock=clock, sleep_ms=clock.sleep)
        summary_text = json.dumps(outcome.summary, sort_keys=True)
        self.assertTrue(outcome.summary["config_gate_passed"])
        self.assertTrue(outcome.summary["collection_complete"])
        self.assertLessEqual(outcome.summary["attempts"], 120)
        self.assertEqual(outcome.summary["wire_attempts"], len(sender.requests))
        self.assertEqual(outcome.summary["attempts"], len(sender.requests))
        self.assertEqual(outcome.summary["window_end_ms"] - outcome.summary["window_start_ms"],
                         86_400_000)
        for request in sender.requests:
            self.assertEqual(request.host, http.GLOBAL_DEMO_HOST)
            self.assertEqual(dict(request.headers)["x-simulated-trading"], "1")
            self.assertLessEqual(request.timeout_ms, 10_000)
        for private in ("credential-key", "credential-secret", "credential-pass",
                        "private-main-uid", "98765.4321", "12345.67"):
            self.assertNotIn(private, summary_text)
        self.assertNotIn("not_subaccount", outcome.summary["discrepancies"])
        self.assertFalse(outcome.summary["expected_uid_independently_matched"])
        self.assertFalse(outcome.summary["reconciled"])
        self.assertFalse(outcome.summary["trade_authorized"])
        self.assertIn("local_attribution_not_loaded", outcome.summary["discrepancies"])

    def test_balance_diagnostic_survives_in_safe_summary_without_private_values(self):
        clock = FakeClock()

        class InvalidBalanceSender(SyntheticSender):
            def send(self, request):
                response = super().send(request)
                if request.target.split("?", 1)[0] == "/api/v5/account/balance":
                    return wire_body([{"totalEq": "PRIVATE-BALANCE-MARKER", "uid": "PRIVATE-UID"}])
                return response

        outcome = demo.run_once(http.MemoryCredentials("k", "s", "p"),
                                sender=InvalidBalanceSender(clock), clock=clock, sleep_ms=clock.sleep)
        self.assertEqual(outcome.summary["record_diagnostics"], [
            {"alias": "balance", "field": "totalEq", "reason": "invalid_decimal", "count": 1},
        ])
        self.assertIn("invalid_record:balance", outcome.summary["discrepancies"])
        self.assertFalse(outcome.summary["reconciled"])
        self.assertFalse(outcome.summary["trade_authorized"])
        for private in ("PRIVATE-BALANCE-MARKER", "PRIVATE-UID", "private-main-uid"):
            self.assertNotIn(private, json.dumps(outcome.summary))

    def test_config_http_failure_stops_without_later_http(self):
        clock = FakeClock()
        sender = SyntheticSender(clock, config_status=500)
        outcome = demo.run_once(http.MemoryCredentials("k", "s", "p"), sender=sender,
                                clock=clock, sleep_ms=clock.sleep)
        self.assertFalse(outcome.summary["collection_complete"])
        self.assertFalse(outcome.summary["config_gate_passed"])
        self.assertEqual(len(sender.requests), 1)
        self.assertEqual(sender.requests[0].target.split("?", 1)[0], "/api/v5/account/config")

    def test_rate_limit_retries_share_attempt_accounting(self):
        clock = FakeClock()
        sender = SyntheticSender(clock, rate_limits=2)
        outcome = demo.run_once(http.MemoryCredentials("k", "s", "p"), sender=sender,
                                clock=clock, sleep_ms=clock.sleep)
        self.assertTrue(outcome.summary["config_gate_passed"])
        self.assertEqual(outcome.summary["wire_attempts"], len(sender.requests))
        self.assertEqual(outcome.summary["attempts"], len(sender.requests))
        self.assertGreaterEqual(outcome.summary["attempts"], 3)
        self.assertLessEqual(outcome.summary["attempts"], 120)

    def test_latency_summary_and_near_runtime_budget_are_synthetic(self):
        clock = FakeClock()

        class SlowSender(SyntheticSender):
            def send(self, request):
                clock.sleep(4900)
                return super().send(request)

        outcome = demo.run_once(http.MemoryCredentials("k", "s", "p"),
            sender=SlowSender(clock), clock=clock, sleep_ms=clock.sleep)
        evidence = outcome.summary["latency_evidence"]
        self.assertFalse(outcome.summary["collection_complete"])
        self.assertFalse(outcome.summary["trade_authorized"])
        self.assertGreaterEqual(evidence["batch_span_ms"], 180000)
        self.assertLessEqual(evidence["batch_span_ms"], 184900)
        self.assertEqual(evidence["report_age_ms"], 0)
        self.assertEqual(evidence["attempts"][-1]["outcome"], "timeout")
        self.assertEqual(evidence["public_time"][0]["server_time_ms"],
                         evidence["attempts"][1]["completed_ms"])

    def test_invalid_public_time_keeps_report_but_provides_no_clock_evidence(self):
        clock = FakeClock()

        class InvalidTimeSender(SyntheticSender):
            def send(self, request):
                if request.target == "/api/v5/public/time":
                    return wire_body([{"ts": "not-a-timestamp"}])
                return super().send(request)

        outcome = demo.run_once(http.MemoryCredentials("k", "s", "p"),
            sender=InvalidTimeSender(clock), clock=clock, sleep_ms=clock.sleep)
        self.assertEqual(outcome.summary["latency_evidence"]["public_time"], [])
        self.assertIn("invalid_record:public_time", outcome.summary["discrepancies"])
        self.assertFalse(outcome.summary["reconciled"])


if __name__ == "__main__":
    unittest.main()
