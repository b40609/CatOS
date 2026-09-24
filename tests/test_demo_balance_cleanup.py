from decimal import Decimal
import hashlib
import hmac
import base64
import json
import unittest
from unittest import mock

from catos.okx_http import MemoryCredentials, WireResponse
from tools import demo_balance_cleanup as cleanup


def detail(ccy, eq, *, avail=None, cash=None, liab="", frozen="0", ord_frozen="0"):
    value = str(eq)
    return {
        "ccy": ccy,
        "eq": value,
        "availBal": value if avail is None else str(avail),
        "cashBal": value if cash is None else str(cash),
        "liab": liab,
        "frozenBal": frozen,
        "ordFrozen": ord_frozen,
    }


class DemoBalanceCleanupTests(unittest.TestCase):
    def test_plan_reduces_only_non_usdt_free_balances(self):
        row = {"details": [
            detail("BTC", "0.1"), detail("ETH", "2"), detail("OKB", "3"),
            detail("USDT", "1000"),
        ]}
        plan = cleanup.plan_reductions(row)
        self.assertEqual(plan, (
            {"ccy": "BTC", "amt": "0.1"},
            {"ccy": "ETH", "amt": "2"},
            {"ccy": "OKB", "amt": "3"},
        ))
        self.assertNotIn("USDT", json.dumps(plan))

    def test_zero_or_absent_targets_are_noop(self):
        row = {"details": [detail("BTC", "0"), detail("USDT", "1000")]}
        self.assertEqual(cleanup.plan_reductions(row), ())

    def test_frozen_liability_or_partial_available_fails_closed(self):
        for item in (
            detail("BTC", "1", liab="0.1"),
            detail("BTC", "1", frozen="0.1"),
            detail("BTC", "1", ord_frozen="0.1"),
            detail("BTC", "1", avail="0.9"),
            detail("BTC", "1", cash="0.9"),
        ):
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    cleanup.plan_reductions({"details": [item, detail("USDT", "1000")]})

    def test_post_signature_binds_method_target_and_body(self):
        creds = MemoryCredentials("key", "secret", "pass")
        body = b'{"adjustments":[{"amt":"1","ccy":"BTC"}],"type":"reduce"}'
        headers = dict(cleanup._post_headers(creds, cleanup.ADJUST_TARGET, body, 0))
        timestamp = "1970-01-01T00:00:00.000Z"
        expected = base64.b64encode(hmac.new(
            b"secret", (timestamp + "POST" + cleanup.ADJUST_TARGET + body.decode()).encode(),
            hashlib.sha256).digest()).decode()
        self.assertEqual(headers["OK-ACCESS-SIGN"], expected)
        self.assertEqual(headers["x-simulated-trading"], "1")

    def test_execute_never_posts_when_identity_preflight_fails(self):
        creds = MemoryCredentials("key", "secret", "pass")
        post = mock.Mock()
        with mock.patch.object(cleanup, "collect_identity", return_value={
            "collection_complete": False, "checks": {}}):
            result = cleanup.execute(creds, get_sender=mock.Mock(), post_sender=post, pause=lambda _: None)
        self.assertEqual(result["status"], "preflight_failed")
        self.assertFalse(result["post_attempted"])
        post.send.assert_not_called()

    def test_verify_cleared_requires_zero_equity(self):
        self.assertTrue(cleanup._verify_cleared({"details": [
            detail("BTC", "0"), detail("ETH", "0"), detail("OKB", "0"), detail("USDT", "1000")]}))
        self.assertFalse(cleanup._verify_cleared({"details": [
            detail("BTC", "0.1"), detail("USDT", "1000")]}))


if __name__ == "__main__":
    unittest.main()
