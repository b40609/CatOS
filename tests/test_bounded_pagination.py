"""Synthetic tests for the I-b-1 offline pagination driver."""

import hashlib
import unittest

from catos import bounded_pagination as p


class FakeClock:
    def __init__(self):
        self.wall = 1_000
        self.mono = 0

    def wall_ms(self):
        return self.wall

    def monotonic_ms(self):
        return self.mono

    def advance(self, ms):
        self.wall += ms
        self.mono += ms


def limits(**changes):
    values = dict(max_requests=5, max_pages=3, request_timeout_ms=50, max_runtime_ms=500)
    values.update(changes)
    return p.Limits(**values)


class PaginationTests(unittest.TestCase):
    def test_timeout_is_capped_to_remaining_runtime(self):
        clock = FakeClock()
        timeouts = []
        def fetch(cursor, timeout):
            timeouts.append(timeout)
            clock.advance(4)
            return p.Page({}, 1, 'next' if cursor is None else None)
        result = p.collect(fetch, limits(request_timeout_ms=1000, max_runtime_ms=10), clock=clock)
        self.assertEqual(timeouts, [10, 6])
        self.assertTrue(result.complete)

    def test_connection_failure_preserves_prior_evidence(self):
        for failure in (ConnectionError('synthetic'), p.TransportError()):
            with self.subTest(failure=type(failure).__name__):
                def fetch(cursor, timeout):
                    if cursor is None:
                        return p.Page({'data': []}, 1, 'next')
                    raise failure
                result = p.collect(fetch, limits(), clock=FakeClock())
                self.assertEqual(result.issue, 'transport_error')
                self.assertEqual((result.requests, len(result.evidence)), (2, 1))

    def test_json_depth_nodes_and_serialized_byte_limits(self):
        cases = [({'a': {'b': {}}}, limits(max_json_depth=1), 'page_depth_limit_exceeded'),
                 ({'a': [1, 2]}, limits(max_json_nodes=3), 'page_node_limit_exceeded'),
                 ({'a': '\n' * 5}, limits(max_json_bytes=12), 'page_byte_limit_exceeded')]
        for payload, budget, expected in cases:
            with self.subTest(expected=expected):
                result = p.collect(lambda *_: p.Page(payload, 1), budget, clock=FakeClock())
                self.assertEqual(result.issue, expected)
                self.assertFalse(result.complete)

    def test_cycle_and_invalid_unicode_return_incomplete(self):
        cyclic = {}; cyclic['self'] = cyclic
        for payload in (cyclic, {'a': '\ud800'}):
            result = p.collect(lambda *_: p.Page(payload, 1), limits(), clock=FakeClock())
            self.assertFalse(result.complete)
            self.assertIn(result.issue, ('page_depth_limit_exceeded', 'malformed_page'))

    def test_limits_must_all_be_explicit_positive_integers(self):
        for change in (
            dict(max_requests=0),
            dict(max_pages=0),
            dict(request_timeout_ms=0),
            dict(max_runtime_ms=0),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                limits(**change)

    def test_cursor_chain_digest_and_source_order_are_preserved(self):
        scripted = [
            p.Page({"code": "0", "data": [{"id": "1"}]}, 200, "next"),
            p.Page({"data": [{"id": "2"}], "code": "0"}, 100),
        ]
        calls = []

        def fetch(cursor, timeout_ms):
            calls.append((cursor, timeout_ms))
            return scripted.pop(0)

        result = p.collect(fetch, limits(), clock=FakeClock())

        self.assertTrue(result.complete)
        self.assertEqual(calls, [(None, 50), ("next", 50)])
        self.assertEqual([item.source_ms for item in result.evidence], [200, 100])
        canonical = '{"code":"0","data":[{"id":"1"}]}'
        self.assertEqual(result.payloads_json[0], canonical)
        self.assertEqual(result.evidence[0].digest, hashlib.sha256(canonical.encode()).hexdigest())

    def test_repeated_cursor_is_incomplete_without_retry(self):
        scripted = [p.Page({}, 1, "a"), p.Page({}, 2, "a")]
        calls = []

        def fetch(cursor, _timeout):
            calls.append(cursor)
            return scripted.pop(0)

        result = p.collect(fetch, limits(), clock=FakeClock())
        self.assertFalse(result.complete)
        self.assertEqual(result.issue, "repeated_cursor")
        self.assertEqual(calls, [None, "a"])
        self.assertEqual(len(result.payloads_json), 2)

    def test_page_limit_preserves_partial_evidence(self):
        scripted = [p.Page({}, 1, "a"), p.Page({}, 2, "b")]
        result = p.collect(lambda _cursor, _timeout: scripted.pop(0), limits(max_pages=2), clock=FakeClock())
        self.assertEqual(result.issue, "page_limit_exhausted")
        self.assertEqual(len(result.evidence), 2)

    def test_request_budget_stops_before_extra_fetch(self):
        calls = []

        def fetch(cursor, _timeout):
            calls.append(cursor)
            return p.Page({}, 1, "next")

        result = p.collect(fetch, limits(max_requests=1), clock=FakeClock())
        self.assertEqual(result.issue, "request_budget_exhausted")
        self.assertEqual(result.requests, 1)
        self.assertEqual(calls, [None])

    def test_timeout_keeps_prior_page_and_does_not_retry(self):
        scripted = [p.Page({}, 1, "next"), TimeoutError("fixture")]

        def fetch(_cursor, _timeout):
            item = scripted.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        result = p.collect(fetch, limits(), clock=FakeClock())
        self.assertEqual(result.issue, "timeout")
        self.assertEqual(result.requests, 2)
        self.assertEqual(len(result.payloads_json), 1)

    def test_late_response_is_timeout_and_not_accepted(self):
        clock = FakeClock()

        def fetch(_cursor, _timeout):
            clock.advance(51)
            return p.Page({}, 1)

        result = p.collect(fetch, limits(), clock=clock)
        self.assertEqual(result.issue, "timeout")
        self.assertFalse(result.payloads_json)

    def test_rate_limit_and_interruption_stop_without_retry(self):
        for failure, issue in ((p.RateLimited(), "rate_limited"), (p.Interrupted(), "interrupted")):
            with self.subTest(issue=issue):
                calls = []

                def fetch(_cursor, _timeout):
                    calls.append(1)
                    raise failure

                result = p.collect(fetch, limits(), clock=FakeClock())
                self.assertEqual(result.issue, issue)
                self.assertEqual(calls, [1])

    def test_explicit_rate_limit_retry_counts_attempts_and_keeps_cursor(self):
        clock = FakeClock()
        calls = []
        sleeps = []
        def sleep(ms):
            sleeps.append(ms)
            clock.advance(ms)
        def fetch(cursor, _timeout):
            calls.append(cursor)
            if len(calls) == 1:
                raise p.RetryableRateLimit(250)
            return p.Page({}, 1)
        result = p.collect(fetch, limits(max_requests=2), clock=clock,
                           retry_policy=p.RetryPolicy(1, 100, 500), sleep_ms=sleep)
        self.assertTrue(result.complete)
        self.assertEqual((result.requests, calls, sleeps), (2, [None, None], [250]))

    def test_retry_wait_over_cap_and_interrupted_sleep_do_not_retry(self):
        result = p.collect(lambda *_: (_ for _ in ()).throw(p.RetryableRateLimit(501)),
                           limits(), clock=FakeClock(), retry_policy=p.RetryPolicy(1, 100, 500))
        self.assertEqual((result.issue, result.requests), ("rate_limited", 1))

        clock = FakeClock()
        calls = []
        def fetch(*_):
            calls.append(1)
            raise p.RetryableRateLimit(100)
        result = p.collect(fetch, limits(), clock=clock,
                           retry_policy=p.RetryPolicy(1, 100, 500), sleep_ms=lambda _ms: None)
        self.assertEqual(result.issue, "interrupted")
        self.assertEqual(calls, [1])

    def test_runtime_limit_preserves_page_but_marks_incomplete(self):
        clock = FakeClock()

        def fetch(_cursor, _timeout):
            clock.advance(500)
            return p.Page({}, 1, "next")

        result = p.collect(fetch, limits(request_timeout_ms=600), clock=clock)
        self.assertEqual(result.issue, "runtime_budget_exhausted")
        self.assertEqual(len(result.payloads_json), 1)

    def test_float_or_non_json_payload_is_rejected(self):
        for payload in ({"value": 1.25}, {"value": object()}):
            with self.subTest(payload=payload):
                result = p.collect(lambda _cursor, _timeout: p.Page(payload, 1), limits(), clock=FakeClock())
                self.assertEqual(result.issue, "malformed_page")
                self.assertFalse(result.payloads_json)


if __name__ == "__main__":
    unittest.main()
