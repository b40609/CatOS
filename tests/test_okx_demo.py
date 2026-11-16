import base64
from decimal import Decimal
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from catos import okx_demo
from catos.okx_demo import Credentials, DemoClient, DemoError, OkxApiError

FAKE = Credentials("fake-key-123", "fake-secret-456", "fake-pass-789")


class FakeSender:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def send(self, method, target, headers, body):
        self.calls.append((method, target, dict(headers), body))
        path = target.split("?", 1)[0]
        doc = self.responses.get((method, path), {"code": "0", "data": []})
        if callable(doc):
            doc = doc(target, body)
        return 200, json.dumps(doc).encode()


def client(sender, ms=1_700_000_000_123):
    return DemoClient(FAKE, sender, clock_ms=lambda: ms, sleep=lambda s: None, monotonic=lambda: 0.0)


class RequestTests(unittest.TestCase):
    def test_every_request_is_demo_and_signed_correctly(self):
        sender = FakeSender()
        c = client(sender)
        sender.responses[("GET", "/api/v5/account/config")] = {"code": "0", "data": [{"acctLv": "2", "posMode": "net_mode", "perm": "read_only,trade"}]}
        c.account_config()
        method, target, headers, body = sender.calls[0]
        self.assertEqual(headers["x-simulated-trading"], "1")
        self.assertEqual(headers["OK-ACCESS-TIMESTAMP"], "2023-11-14T22:13:20.123Z")
        expected = base64.b64encode(hmac.new(b"fake-secret-456", b"2023-11-14T22:13:20.123ZGET/api/v5/account/config",
                                             hashlib.sha256).digest()).decode()
        self.assertEqual(headers["OK-ACCESS-SIGN"], expected)

    def test_public_requests_carry_no_credentials_but_still_demo(self):
        sender = FakeSender({("GET", "/api/v5/public/mark-price"): {"code": "0", "data": [{"markPx": "95000.1"}]}})
        self.assertEqual(client(sender).mark_price(), Decimal("95000.1"))
        headers = sender.calls[0][2]
        self.assertEqual(headers["x-simulated-trading"], "1")
        self.assertNotIn("OK-ACCESS-KEY", headers)

    def test_non_whitelisted_endpoints_are_refused_before_sending(self):
        sender = FakeSender()
        c = client(sender)
        for method, path in (("POST", "/api/v5/account/set-leverage"), ("POST", "/api/v5/account/set-position-mode"),
                             ("POST", "/api/v5/asset/withdrawal"), ("GET", "/api/v5/asset/balances"),
                             ("DELETE", "/api/v5/trade/order")):
            with self.assertRaises(DemoError):
                c._request(method, path)
        self.assertEqual(sender.calls, [])

    def test_market_order_forces_tag_cross_and_signs_body(self):
        sender = FakeSender({("POST", "/api/v5/trade/order"): {"code": "0", "data": [{"ordId": "111", "sCode": "0"}]}})
        ord_id = client(sender).place_market_order("BTC-USDT-SWAP", "buy", Decimal("0.01"), cl_ord_id="catos1")
        self.assertEqual(ord_id, "111")
        _, target, headers, body = sender.calls[0]
        payload = json.loads(body)
        self.assertEqual(payload, {"instId": "BTC-USDT-SWAP", "tdMode": "cross", "side": "buy", "ordType": "market",
                                   "sz": "0.01", "tag": okx_demo.TAG, "clOrdId": "catos1"})
        expected = base64.b64encode(hmac.new(b"fake-secret-456",
            ("2023-11-14T22:13:20.123ZPOST/api/v5/trade/order" + body.decode()).encode(), hashlib.sha256).digest()).decode()
        self.assertEqual(headers["OK-ACCESS-SIGN"], expected)

    def test_reduce_only_and_input_validation(self):
        sender = FakeSender({("POST", "/api/v5/trade/order"): {"code": "0", "data": [{"ordId": "2", "sCode": "0"}]}})
        c = client(sender)
        c.place_market_order("BTC-USDT-SWAP", "sell", Decimal("0.01"), reduce_only=True)
        self.assertTrue(json.loads(sender.calls[0][3])["reduceOnly"])
        for args in (("BTC-USDT-SWAP", "long", Decimal("1")), ("BTC-USDT-SWAP", "buy", Decimal("0")),
                     ("BTC-USDT-SWAP", "buy", 1.0), ("BTC-USD-SWAP", "buy", Decimal("1")),
                     ("BTC-USDT", "buy", Decimal("1"))):
            with self.assertRaises(DemoError):
                c.place_market_order(*args)
        self.assertEqual(len(sender.calls), 1)

    def test_order_rejection_surfaces_scode(self):
        sender = FakeSender({("POST", "/api/v5/trade/order"): {"code": "1", "msg": "All operations failed",
                                                                "data": [{"ordId": "", "sCode": "51008", "sMsg": "Insufficient margin"}]}})
        with self.assertRaises(OkxApiError) as ctx:
            client(sender).place_market_order("BTC-USDT-SWAP", "buy", Decimal("1"))
        self.assertEqual(ctx.exception.code, "51008")

    def test_errors_never_contain_credentials(self):
        class Boom:
            def send(self, *a):
                raise RuntimeError("fake-secret-456 fake-key-123")
        with self.assertRaises(DemoError) as ctx:
            client(Boom()).account_config()
        self.assertNotIn("fake", str(ctx.exception))
        self.assertNotIn("fake", repr(FAKE))
        self.assertNotIn("fake", repr(client(FakeSender())))

    def test_spacing_between_requests(self):
        waits = []
        now = [0.0]
        c = DemoClient(FAKE, FakeSender(), clock_ms=lambda: 0, sleep=waits.append, monotonic=lambda: now[0])
        c._request("GET", "/api/v5/public/time")
        now[0] = 0.1
        c._request("GET", "/api/v5/public/time")
        self.assertAlmostEqual(waits[0], 0.15)


class StatusTests(unittest.TestCase):
    def responses(self, **config):
        cfg = {"acctLv": "2", "posMode": "net_mode", "perm": "read_only,trade"}
        cfg.update(config)
        return {
            ("GET", "/api/v5/account/config"): {"code": "0", "data": [cfg]},
            ("GET", "/api/v5/account/balance"): {"code": "0", "data": [{"totalEq": "10000.5", "details": [
                {"ccy": "USDT", "eq": "10000.5", "availEq": "9900"}]}]},
            ("GET", "/api/v5/account/positions"): {"code": "0", "data": [
                {"instId": "BTC-USDT-SWAP", "pos": "0.01", "mgnMode": "cross", "posSide": "net", "avgPx": "95000", "upl": "1.2"},
                {"instId": "ETH-USDT-SWAP", "pos": "0", "mgnMode": "cross"}]},
            ("GET", "/api/v5/trade/orders-pending"): {"code": "0", "data": []},
        }

    def test_status_reads_decimals_and_skips_flat_positions(self):
        report = okx_demo.status(client(FakeSender(self.responses())))
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["balance"]["usdt_avail"], Decimal("9900"))
        self.assertEqual([p["pos"] for p in report["positions"]], [Decimal("0.01")])
        text = okx_demo.render_status(report)
        self.assertIn("10000.5", text)
        self.assertIn("可以下單", text)

    def test_status_flags_withdraw_hedge_mode_and_simple_account(self):
        report = okx_demo.status(client(FakeSender(self.responses(perm="read_only,withdraw,trade",
                                                                  posMode="long_short_mode", acctLv="1"))))
        self.assertEqual(len(report["issues"]), 3)
        self.assertIn("不能下單", okx_demo.render_status(report))

    def test_status_never_sends_writes(self):
        sender = FakeSender(self.responses())
        okx_demo.status(client(sender))
        self.assertTrue(all(call[0] == "GET" for call in sender.calls))


class FakeOkx:
    """記狀態的假模擬盤：市價單立即成交在 100，每次手續費 0.0005。"""

    def __init__(self, pos="0", pending=(), perm="read_only,trade", fill_states=("filled",), reject_close=False):
        self.pos = Decimal(pos)
        self.eq = Decimal("1000")
        self.pending = list(pending)
        self.perm = perm
        self.orders = {}
        self.posts = []
        self.fill_states = list(fill_states)
        self.reject_close = reject_close

    def send(self, method, target, headers, body):
        assert headers["x-simulated-trading"] == "1"
        path = target.split("?", 1)[0]
        ok = lambda data: (200, json.dumps({"code": "0", "data": data}).encode())
        if path == "/api/v5/account/config":
            return ok([{"acctLv": "2", "posMode": "net_mode", "perm": self.perm}])
        if path == "/api/v5/account/positions":
            return ok([{"instId": "BTC-USDT-SWAP", "pos": format(self.pos, "f"), "mgnMode": "cross"}] if self.pos else [])
        if path == "/api/v5/trade/orders-pending":
            return ok(self.pending)
        if path == "/api/v5/public/instruments":
            return ok([{"instId": "BTC-USDT-SWAP", "ctVal": "0.01", "lotSz": "0.01", "minSz": "0.01", "tickSz": "0.1", "state": "live"}])
        if path == "/api/v5/account/balance":
            return ok([{"totalEq": format(self.eq, "f"), "details": [{"ccy": "USDT", "eq": format(self.eq, "f"), "availEq": format(self.eq, "f")}]}])
        if method == "POST" and path == "/api/v5/trade/order":
            p = json.loads(body)
            self.posts.append(p)
            if p.get("reduceOnly") and self.reject_close:
                return 200, json.dumps({"code": "1", "data": [{"sCode": "51000", "sMsg": "nope"}]}).encode()
            ord_id = str(len(self.orders) + 1)
            size = Decimal(p["sz"])
            self.pos += size if p["side"] == "buy" else -size
            fee = Decimal("-0.0005")
            pnl = Decimal("0.02") if p.get("reduceOnly") else Decimal(0)
            self.eq += fee + pnl
            state = self.fill_states.pop(0) if self.fill_states else "filled"
            self.orders[ord_id] = {"ordId": ord_id, "state": state, "side": p["side"], "sz": p["sz"],
                                   "accFillSz": p["sz"], "avgPx": "100", "fee": format(fee, "f"),
                                   "pnl": format(pnl, "f"), "tag": p["tag"]}
            return ok([{"ordId": ord_id, "sCode": "0"}])
        if path == "/api/v5/trade/order":
            ord_id = dict(x.split("=") for x in target.split("?", 1)[1].split("&"))["ordId"]
            return ok([self.orders[ord_id]])
        raise AssertionError(target)


class FirstOrderTests(unittest.TestCase):
    def run_first(self, fake):
        return okx_demo.first_order(client(fake), sleep=lambda s: None, stamp="1")

    def test_opens_min_size_closes_reduce_only_and_balances(self):
        fake = FakeOkx()
        report = self.run_first(fake)
        self.assertEqual(fake.pos, 0)
        self.assertEqual([(p["side"], p["sz"], p.get("reduceOnly", False), p["tag"]) for p in fake.posts],
                         [("buy", "0.01", False, okx_demo.TAG), ("sell", "0.01", True, okx_demo.TAG)])
        self.assertEqual(report["position_after_open"], Decimal("0.01"))
        self.assertEqual(report["usdt_eq_change"], Decimal("0.0190"))
        self.assertTrue(report["balance_matches"])
        self.assertIn("餘額核對：相符", okx_demo.render_first_order(report))

    def test_refuses_when_position_or_pending_or_bad_key(self):
        for fake in (FakeOkx(pos="0.5"), FakeOkx(pending=[{"instId": "BTC-USDT-SWAP", "ordId": "9"}]),
                     FakeOkx(perm="read_only,trade,withdraw")):
            with self.assertRaises(okx_demo.FirstOrderStop):
                self.run_first(fake)
            self.assertEqual(fake.posts, [])

    def test_open_not_filled_stops_and_tries_reduce_only_close(self):
        fake = FakeOkx(fill_states=["canceled"])
        with self.assertRaises(okx_demo.FirstOrderStop) as ctx:
            self.run_first(fake)
        self.assertEqual(fake.posts[-1]["reduceOnly"], True)
        self.assertEqual(fake.pos, 0)
        self.assertIn("被取消", str(ctx.exception))

    def test_close_rejected_reports_position_may_remain(self):
        fake = FakeOkx(reject_close=True)
        with self.assertRaises(okx_demo.FirstOrderStop) as ctx:
            self.run_first(fake)
        self.assertIn("部位可能還在", str(ctx.exception))
        self.assertEqual(len(fake.posts), 2)


class CredentialFileTests(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_loads_exact_three_fields(self):
        path = self.write(json.dumps({"api_key": "k1", "secret": "s1", "passphrase": "p1"}))
        self.assertEqual(okx_demo.load_credentials(path).api_key, "k1")

    def test_bad_files_fail_without_echoing_contents(self):
        for text in ('{"api_key": "SECRETVALUE", "secret": "s"}', "SECRETVALUE", '{"api_key": "SECRET VALUE", "secret": "s", "passphrase": "p"}',
                     json.dumps({"api_key": "SECRETVALUE", "secret": "s", "passphrase": "p", "extra": 1})):
            with self.assertRaises(DemoError) as ctx:
                okx_demo.load_credentials(self.write(text))
            self.assertNotIn("SECRET", str(ctx.exception))

    def test_missing_file_names_the_path(self):
        with self.assertRaises(DemoError) as ctx:
            okx_demo.load_credentials(Path(tempfile.gettempdir()) / "catos-no-such-file.json")
        self.assertIn("catos-no-such-file.json", str(ctx.exception))

    def test_path_order_env_then_catos_then_desktop(self):
        with mock.patch.dict(os.environ, {okx_demo.CREDENTIALS_ENV: "X:/elsewhere.json"}):
            self.assertEqual(okx_demo.credentials_path(), Path("X:/elsewhere.json"))
        with tempfile.TemporaryDirectory() as home, mock.patch.object(Path, "home", return_value=Path(home)), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(okx_demo.CREDENTIALS_ENV, None)
            primary = Path(home) / ".catos" / "okx-demo.json"
            desktop = Path(home) / "Desktop" / "OKX_API.txt"
            self.assertEqual(okx_demo.credentials_path(), primary)
            desktop.parent.mkdir()
            desktop.write_text("x")
            self.assertEqual(okx_demo.credentials_path(), desktop)
            primary.parent.mkdir()
            primary.write_text("x")
            self.assertEqual(okx_demo.credentials_path(), primary)

    TEXT = ("Demo\napikey = k-one\nsecretkey = s-one\npassphrase = p-one\nIP = \n權限 讀取/交易\n\n"
            "Demo\napikey = k-two\nsecretkey = s-two\npassphrase = p-two\nIP = \n備註名稱 catOSv1_Demo\n")

    def test_labelled_text_with_several_sets(self):
        sets = okx_demo.load_credential_sets(self.write(self.TEXT))
        self.assertEqual([c.api_key for c in sets], ["k-one", "k-two"])
        self.assertEqual(sets[1].secret, "s-two")
        with self.assertRaises(DemoError):
            okx_demo.load_credentials(self.write(self.TEXT))

    def test_labelled_text_rejects_incomplete_or_duplicate(self):
        for text in ("apikey = SECRETA\npassphrase = p\n", "secretkey = SECRETA\napikey = k\npassphrase = p\n",
                     "apikey = k\nsecretkey = SECRETA\nsecretkey = SECRETB\npassphrase = p\n"):
            with self.assertRaises(DemoError) as ctx:
                okx_demo.load_credential_sets(self.write(text))
            self.assertNotIn("SECRET", str(ctx.exception))

    def config_sender(self, working_keys):
        class Sender:
            def send(self, method, target, headers, body):
                if headers.get("OK-ACCESS-KEY") in working_keys:
                    return 200, json.dumps({"code": "0", "data": [{"label": "lab-" + headers["OK-ACCESS-KEY"],
                                                                   "perm": "read_only,trade"}]}).encode()
                return 200, json.dumps({"code": "50119", "msg": "API key doesn't exist", "data": []}).encode()
        return Sender()

    def test_connect_picks_the_only_working_set(self):
        client, note = okx_demo.connect(self.write(self.TEXT), sender=self.config_sender({"k-two"}))
        self.assertEqual(client._credentials.api_key, "k-two")
        self.assertIn("第 2 組", note)
        self.assertIn("lab-k-two", note)
        self.assertNotIn("s-two", note)

    def test_connect_refuses_when_zero_or_several_work(self):
        for working in (set(), {"k-one", "k-two"}):
            with self.assertRaises(DemoError):
                okx_demo.connect(self.write(self.TEXT), sender=self.config_sender(working))

    def test_cli_reports_missing_key_file(self):
        with mock.patch.dict(os.environ, {okx_demo.CREDENTIALS_ENV: str(Path(tempfile.gettempdir()) / "catos-none.json")}):
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                from catos.cli import main
                self.assertEqual(main(["demo", "status"]), 1)
        self.assertIn("找不到金鑰檔", err.getvalue())


if __name__ == "__main__":
    unittest.main()
