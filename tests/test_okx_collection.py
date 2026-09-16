"""I-b-1 contract tests use synthetic identifiers only."""

import unittest

from catos import okx_collection as c
from test_bounded_pagination import FakeClock


def scope(**changes):
    values = dict(
        account_alias="fixture-sub",
        environment="demo",
        instrument="BTC-USDT-SWAP",
        window_start_ms=100,
        window_end_ms=200,
        max_requests=10,
        max_pages_per_endpoint=3,
        request_timeout_ms=50,
        max_runtime_ms=500,
    )
    values.update(changes)
    return c.RunScope(**values)


class CollectionContractTests(unittest.TestCase):
    def test_plan_is_immutable_and_request_cannot_bypass_allowlist(self):
        for aliases in (['balance'], ('balance', [])):
            with self.assertRaises(ValueError):
                c.CollectionPlan(scope(), aliases)
        with self.assertRaises(ValueError):
            c.EndpointSpec('balance', '/api/v5/account/balance', method='POST')
        with self.assertRaises(ValueError):
            c.PageRequest(c.EndpointSpec('balance', '/api/v5/trade/order'), scope(), 1, None, 1)
        for page, timeout in ((0, 1), (1, 0), (4, 1), (1, 51)):
            with self.assertRaises(ValueError):
                c.PageRequest(c.ENDPOINTS['balance'], scope(), page, None, timeout)

    def test_scope_requires_demo_usdt_swap_window_and_budgets(self):
        for change in (
            dict(account_alias=""),
            dict(environment="live"),
            dict(instrument="BTC-USD-SWAP"),
            dict(window_end_ms=100),
            dict(max_requests=0),
            dict(max_pages_per_endpoint=0),
            dict(request_timeout_ms=0),
            dict(max_runtime_ms=0),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                scope(**change)

    def test_plan_rejects_unknown_duplicate_or_empty_endpoints(self):
        for aliases in ((), ("unknown",), ("balance", "balance")):
            with self.subTest(aliases=aliases), self.assertRaises(ValueError):
                c.CollectionPlan(scope(), aliases)

    def test_allowlist_contains_only_fixed_get_api_paths(self):
        self.assertEqual(c.ENDPOINTS["balance"].path, "/api/v5/account/balance")
        self.assertEqual(c.ENDPOINTS["orders_history"].path, "/api/v5/trade/orders-history")
        for spec in c.ENDPOINTS.values():
            self.assertEqual(spec.method, "GET")
            self.assertTrue(spec.path.startswith("/api/v5/"))
            self.assertNotIn("://", spec.path)

    def test_page_request_carries_scope_timeout_and_opaque_cursor(self):
        selected = scope()
        request = c.PageRequest(c.ENDPOINTS["fills_history"], selected, 2, "cursor-token", 50)
        self.assertIs(request.scope, selected)
        self.assertEqual(request.page_number, 2)
        self.assertEqual(request.cursor, "cursor-token")
        self.assertEqual(request.timeout_ms, 50)


class CollectionIntegrationTests(unittest.TestCase):
    def collect(self, outcomes, aliases=('balance', 'positions'), selected=None, clock=None):
        self.calls = []
        class Transport:
            def fetch(_, request):
                self.calls.append(request)
                outcome = outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome(request) if callable(outcome) else outcome
        return c.collect_plan(c.CollectionPlan(selected or scope(), aliases), Transport(), clock=clock or FakeClock())

    def page(self, cursor=None, **changes):
        return c.PageResponse(**(dict(account_alias='fixture-sub', environment='demo', source_ms=100,
                                     payload={'code': '0', 'data': []}, next_cursor=cursor) | changes))

    def test_batch_manifest_binds_scope_pages_and_digests(self):
        result = self.collect([self.page('a'), self.page(), self.page()])
        self.assertTrue(result.manifest.complete)
        self.assertEqual(result.manifest.requests, 3)
        self.assertEqual((result.manifest.account_alias, result.manifest.environment, result.manifest.instrument),
                         ('fixture-sub', 'demo', 'BTC-USDT-SWAP'))
        self.assertEqual([r.cursor for r in self.calls], [None, 'a', None])
        self.assertEqual([r.page_number for r in self.calls], [1, 2, 1])
        self.assertEqual(len(result.manifest.endpoint_manifests[0].pages), 2)
        self.assertEqual(len(result.manifest.endpoint_manifests[0].pages[0].digest), 64)

    def test_request_budget_shared_and_unstarted_endpoint_recorded(self):
        result = self.collect([self.page()], selected=scope(max_requests=1))
        self.assertEqual(len(self.calls), 1)
        last = result.manifest.endpoint_manifests[1]
        self.assertEqual(last.issue, 'not_started:request_budget_exhausted')
        self.assertIsNone(last.started_ms)
        self.assertFalse(result.manifest.complete)

    def test_runtime_shared_across_endpoints(self):
        clock = FakeClock()
        def respond(request):
            clock.advance(6)
            return self.page()
        result = self.collect([respond, respond], selected=scope(max_runtime_ms=10), clock=clock)
        self.assertEqual([r.timeout_ms for r in self.calls], [10, 4])
        self.assertFalse(result.manifest.complete)
        self.assertEqual(len(result.pages), 1)  # Late second response is not accepted.

    def test_scope_mismatch_is_not_saved_and_stops_entire_run(self):
        for changes in (dict(account_alias='other'), dict(environment='live')):
            result = self.collect([self.page('a'), self.page(**changes)])
            self.assertEqual(len(result.pages), 1)
            self.assertEqual(len(self.calls), 2)
            self.assertEqual(result.manifest.endpoint_manifests[0].issue, 'scope_mismatch')
            self.assertEqual(result.manifest.endpoint_manifests[1].issue, 'not_started:scope_mismatch')

    def test_rate_limit_and_interruption_do_not_start_other_endpoint(self):
        for error, expected in ((c.RateLimited(), 'rate_limited'), (c.CollectionInterrupted(), 'interrupted')):
            result = self.collect([error])
            self.assertEqual(result.manifest.endpoint_manifests[0].issue, expected)
            self.assertEqual(len(self.calls), 1)
            self.assertFalse(result.manifest.complete)

    def test_api_failure_is_not_complete_empty_account(self):
        result = self.collect([self.page(payload={'code': '50000', 'msg': 'not stored', 'data': []}), self.page()])
        self.assertFalse(result.manifest.complete)
        self.assertEqual(result.manifest.endpoint_manifests[0].issue, 'api_error')
        self.assertEqual(len(result.pages), 1)

    def test_page_limit_preserves_partial_and_continues_other_source(self):
        result = self.collect([self.page('a'), self.page()], selected=scope(max_pages_per_endpoint=1))
        self.assertEqual(result.manifest.endpoint_manifests[0].issue, 'page_limit_exhausted')
        self.assertTrue(result.manifest.endpoint_manifests[1].complete)
        self.assertFalse(result.manifest.complete)

    def test_transport_error_keeps_pages_and_later_sources(self):
        result = self.collect([self.page('a'), ConnectionError('private message not stored'), self.page()])
        self.assertEqual(result.manifest.requests, 3)
        self.assertEqual(len(result.pages), 2)
        self.assertEqual(result.manifest.endpoint_manifests[0].issue, 'transport_error')
        self.assertNotIn('private', repr(result))


if __name__ == "__main__":
    unittest.main()
