"""Synthetic protocol and schema checks, with no strategy import."""

import asyncio
from dataclasses import replace
from decimal import Decimal, localcontext
import io
import struct
import unittest

from catos import ipc
from catos.research import AccountView, Candle, ContractSpec

D = Decimal
STEP = 900_000


def config(warmup=2):
    return ipc.WorkerConfig(ContractSpec("SYNTHETIC-USDT-SWAP", D("0.01"),
                                        D("0.01"), D("1"), D("1")), STEP, warmup)


def bar(index, price="100"):
    price = D(price)
    return Candle(index * STEP, price, price, price, price)


def account(index):
    return AccountView((index + 1) * STEP, D("0"), D("0"), D("1000"),
                       D("0"), D("0"), D("1000"), D("0"), D("0"))


class ShortIO(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2))

    def write(self, data):
        return super().write(data[:3])


class IPCTests(unittest.TestCase):
    def test_partial_sync_io_and_consecutive_frames(self):
        output = ShortIO()
        values = [{"text": "中文\\\"[]{}", "value": "0.000000000000000001"}, {"target": None}]
        for value in values:
            ipc.write_frame_sync(output, value)
        output.seek(0)
        self.assertEqual([ipc.read_frame_sync(output), ipc.read_frame_sync(output)], values)
        with self.assertRaisesRegex(ipc.ProtocolError, "EOF"):
            ipc.read_frame_sync(output)

    def test_truncation_and_frame_limits(self):
        for raw in (b"", b"\x00", struct.pack("!I", 10) + b"{}",
                    struct.pack("!I", 0), struct.pack("!I", ipc.MAX_FRAME + 1)):
            with self.subTest(raw=raw), self.assertRaises(ipc.ProtocolError):
                ipc.read_frame_sync(io.BytesIO(raw))
        with self.assertRaises(ipc.ProtocolError):
            ipc.encode_frame({"x": "x" * ipc.MAX_FRAME})

    def test_json_rejects_duplicates_floats_numbers_and_invalid_text(self):
        bad = [b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":1.0}',
               b'{"x":NaN}', b'{"x":Infinity}', b'{"x":12345678901234567890}',
               b'{"x":9223372036854775808}', b'[]', b'{"x":"\xff"}', b'{oops']
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ipc.ProtocolError):
                ipc.decode_payload(raw)
        for value in ({"x": 1.0}, {"x": D("1")}, {1: "x"}, {"x": object()}):
            with self.assertRaises(ipc.ProtocolError):
                ipc.encode_frame(value)

    def test_nesting_bound_before_decode_and_encode(self):
        with self.assertRaisesRegex(ipc.ProtocolError, "nesting"):
            ipc.decode_payload(b'{"x":' + b'[' * 1000 + b'0' + b']' * 1000 + b'}')
        value = 0
        for _ in range(9):
            value = {"x": value}
        with self.assertRaisesRegex(ipc.ProtocolError, "nesting"):
            ipc.encode_frame(value)
        self.assertEqual(ipc.decode_payload(b'{"x":"[[[[[[[[[[[[["}')["x"], "[" * 13)

    def test_decimal_string_precision_and_context_isolation(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(ipc.decimal_text("100.123456789012345678", "price"), D("100.123456789012345678"))
            value = "0." + "1234567890" * 5
            self.assertEqual(ipc.decimal_text(value, "equity", derived=True), D(value))
            self.assertEqual(context.prec, 2)
        for value in (0, 1.0, True, "NaN", "Infinity", "1_000", " 1", "1e9999", "1e-9999", "1" * 193):
            with self.subTest(value=value), self.assertRaises(ipc.ProtocolError):
                ipc.decimal_text(value, "price")

    def test_config_and_checkpoint_bind_artifact_and_parameters(self):
        cfg = config()
        self.assertEqual(ipc.WorkerConfig.from_wire(cfg.to_wire()), cfg)
        checkpoint = ipc.Checkpoint(cfg, 2, STEP, (D("100.00"), D("101.00")))
        self.assertEqual(ipc.Checkpoint.from_wire(checkpoint.to_wire(), cfg), checkpoint)
        for mutate in (
            lambda value: value.update(strategy_id="arbitrary-module"),
            lambda value: value.update(strategy_version=True),
            lambda value: value.update(timeframe_ms=True),
            lambda value: value.update(warmup_bars=-1),
            lambda value: value.update(tag="forged"),
            lambda value: value["contract"].update(tick_size=0.01),
        ):
            value = cfg.to_wire()
            mutate(value)
            with self.assertRaises(ipc.ProtocolError):
                ipc.WorkerConfig.from_wire(value)
        with self.assertRaisesRegex(ipc.ProtocolError, "mismatch"):
            ipc.Checkpoint.from_wire(checkpoint.to_wire(), config(3))
        with self.assertRaises(ipc.ProtocolError):
            replace(checkpoint, closes=(100.0, 101.0)).to_wire()
        for changes in ({"closes": []}, {"event_seq": 99}, {"last_open_time_ms": None}):
            value = checkpoint.to_wire()
            value.update(changes)
            with self.assertRaises(ipc.ProtocolError):
                ipc.Checkpoint.from_wire(value, cfg)

    def test_envelope_rejects_impersonation_and_wrong_identity(self):
        message = ipc.envelope("bar", "generation1", 1, {})
        for changes in ({"bot_id": "other"}, {"generation": "old"}, {"seq": True},
                        {"seq": 2}, {"version": 2}, {"kind": "result"}):
            with self.subTest(changes=changes), self.assertRaises(ipc.ProtocolError):
                ipc.check_envelope(dict(message, **changes), "bar", "generation1", 1)

    def test_event_validation_prevents_gap_open_bar_and_future_account(self):
        cfg = config()
        cp = ipc.Checkpoint(cfg, 2, STEP, (D("100"), D("100")))
        payload = dict(bar=ipc.bar_to_wire(bar(2)), account=ipc.account_to_wire(account(2)))
        parsed_bar, parsed_account, warmup = ipc.parse_event(payload, cp)
        self.assertEqual((parsed_bar, parsed_account, warmup), (bar(2), account(2), False))
        for changed_bar in (bar(1), bar(3), replace(bar(2), closed=False),
                            replace(bar(2), high=D("99")), replace(bar(2), close=D("100.001"))):
            with self.assertRaises(ipc.ProtocolError):
                ipc.parse_event(dict(payload, bar=ipc.bar_to_wire(changed_bar)), cp)
        with self.assertRaises(ipc.ProtocolError):
            ipc.parse_event(dict(payload, account=ipc.account_to_wire(account(3))), cp)

    def test_warmup_intents_forbidden_and_none_distinct_from_zero(self):
        cfg = config()
        initial = ipc.Checkpoint(cfg)
        cp1 = ipc.Checkpoint(cfg, 1, 0, (D("100"),))
        payload = dict(target=None, checkpoint=cp1.to_wire(), ready=False)
        result = ipc.parse_result(payload, initial, bar(0), None, True)
        self.assertIsNone(result.target_position)
        with self.assertRaisesRegex(ipc.ProtocolError, "warm-up"):
            ipc.parse_result(dict(payload, target="0"), initial, bar(0), None, True)
        cp2 = ipc.Checkpoint(cfg, 2, STEP, (D("100"), D("100")))
        cp3 = ipc.Checkpoint(cfg, 3, 2 * STEP, (D("100"), D("100")))
        payload = dict(target="0", checkpoint=cp3.to_wire(), ready=True)
        self.assertEqual(ipc.parse_result(payload, cp2, bar(2), account(2), False).target_position, D("0"))
        self.assertIsNone(ipc.parse_result(dict(payload, target=None), cp2, bar(2), account(2), False).target_position)
        for changes in ({"target": 0}, {"target": "0.5"}, {"ready": 1}, {"tag": "bad"}):
            with self.assertRaises(ipc.ProtocolError):
                ipc.parse_result(dict(payload, **changes), cp2, bar(2), account(2), False)

    def test_parent_checks_checkpoint_window_and_readiness(self):
        cfg = config()
        cp = ipc.Checkpoint(cfg, 1, 0, (D("100"),))
        bad = ipc.Checkpoint(cfg, 2, STEP, (D("99"), D("101")))
        with self.assertRaisesRegex(ipc.ProtocolError, "correspond"):
            ipc.parse_result(dict(target=None, checkpoint=bad.to_wire(), ready=True),
                             cp, bar(1, "101"), None, True)
        with self.assertRaisesRegex(ipc.ProtocolError, "ready"):
            ipc.Checkpoint.from_wire(ipc.Checkpoint(config(1), 1, 0, (D("100"),)).to_wire(), config(1))


class AsyncFrameTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_async_stream(self):
        reader = asyncio.StreamReader()
        raw = ipc.encode_frame({"target": "2"}) + ipc.encode_frame({"target": None})

        async def feed():
            for offset in range(0, len(raw), 3):
                reader.feed_data(raw[offset:offset + 3])
                await asyncio.sleep(0)
            reader.feed_eof()

        task = asyncio.create_task(feed())
        self.assertEqual(await ipc.read_frame(reader), {"target": "2"})
        self.assertEqual(await ipc.read_frame(reader), {"target": None})
        await task
        with self.assertRaises(ipc.ProtocolError):
            await ipc.read_frame(reader)


if __name__ == "__main__":
    unittest.main()
