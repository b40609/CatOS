import json
import unittest
from urllib.parse import urlsplit, parse_qs

from catos.okx_http import MemoryCredentials, WireResponse
from tools.demo_subaccount_evidence import collect, ALGO_TYPES, parse_explicit_demo_block


class Sender:
    def __init__(self, uid="child", positions=None, error_partition=None):
        self.uid, self.positions = uid, positions or []
        self.error_partition = error_partition
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        self.assert_headers(request)
        parsed = urlsplit(request.target)
        query = parse_qs(parsed.query)
        assert "instId" not in query and "instType" not in query
        data = []
        code = "0"
        if parsed.path.endswith("/config"):
            data = [dict(uid=self.uid, mainUid="parent", posMode="net_mode",
                         acctLv="2", perm="read_only", roleType="0")]
        elif parsed.path.endswith("/positions"):
            data = self.positions
        elif query.get("ordType") == [self.error_partition]:
            code = "1"
        return WireResponse(200, (), json.dumps(dict(code=code, data=data)).encode())

    @staticmethod
    def assert_headers(request):
        assert dict(request.headers)["x-simulated-trading"] == "1"
        assert request.host == "openapi.okx.com"


class EvidenceTests(unittest.TestCase):
    def test_explicit_demo_block_selection_and_ambiguity(self):
        source = ("Live API\nAPI Key=live-key\nSecret Key=live-secret\nPassphrase=live-pass\n"
                  "\nDemo API\nAPI Key=demo-key\nSecret Key=demo-secret\nPassphrase=demo-pass\n")
        credentials = parse_explicit_demo_block(source)
        self.assertEqual(credentials.api_key, "demo-key")
        with self.assertRaises(ValueError):
            parse_explicit_demo_block(source + "\nDemo backup\nAPI Key=other\nSecret Key=other\nPassphrase=other\n")

    def run_slice(self, sender):
        return collect(MemoryCredentials("fake-key", "fake-secret", "fake-pass"),
                       "child", sender=sender, pause=lambda _: None)

    def test_empty_remote_does_not_clear_local_unknown(self):
        sender = Sender()
        result = self.run_slice(sender)
        self.assertEqual(len(sender.requests), 10)
        self.assertTrue(result["collection_complete"])
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["reconciled"])
        self.assertFalse(result["trade_authorized"])
        self.assertIn("unverified", result["local_unknown"])
        serialized = json.dumps(result)
        for private in ("child", "parent", "fake-key", "fake-secret", "fake-pass"):
            self.assertNotIn(private, serialized)

    def test_wrong_identity_stops_after_config(self):
        sender = Sender(uid="parent")
        result = self.run_slice(sender)
        self.assertEqual(len(sender.requests), 1)
        self.assertFalse(result["checks"]["expected_uid"])
        self.assertFalse(result["checks"]["dedicated_subaccount"])
        self.assertFalse(result["collection_complete"])

    def test_foreign_non_swap_record_is_not_filtered_out(self):
        result = self.run_slice(Sender(positions=[{"instType": "FUTURES", "pos": "1"}]))
        self.assertFalse(result["checks"]["no_remote_position_records"])
        self.assertEqual(result["status"], "remote_responsibility_not_empty")

    def test_partition_error_never_becomes_empty_pass(self):
        result = self.run_slice(Sender(error_partition=ALGO_TYPES[-1]))
        self.assertFalse(result["collection_complete"])
        self.assertNotIn("no_remote_algos", result["checks"])
        self.assertEqual(result["status"], "incomplete_fixed_error")


if __name__ == "__main__":
    unittest.main()
