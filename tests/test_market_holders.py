import unittest
from decimal import Decimal

from catos.market_collectors import MarketCollectionError
from catos.market_holders import (
    HOLDER_CONTRACT,
    HOLDER_COST_CONTRACT,
    HolderAddress,
    HolderScope,
    collect_blockscout_address_cost_reference,
    collect_blockscout_holder_snapshot,
    dealer_chip,
    parse_blockscout_address_cost_reference,
    parse_blockscout_holder_snapshot,
)


SYMBOL = "WETH-USDT-SWAP"
CONTRACT = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
EOA = "0x" + "aa" * 20
TX1 = "0x" + "11" * 32
TX2 = "0x" + "22" * 32


def token_payload(*, holders="12", total_supply="1000000"):
    return {
        "address": CONTRACT,
        "type": "ERC-20",
        "total_supply": total_supply,
        "holders": holders,
    }


def holder_payload(values, *, next_page=None):
    return {
        "items": [
            {"address": {"hash": f"0x{index + 1:040x}"}, "value": str(value)}
            for index, value in enumerate(values)
        ],
        "next_page_params": next_page,
    }


def transfer(*, token, decimals, value, from_address, to_address, tx_hash):
    return {
        "from": {"hash": from_address},
        "to": {"hash": to_address},
        "token": {"address_hash": token},
        "total": {"decimals": str(decimals), "value": str(value)},
        "transaction_hash": tx_hash,
    }


def history(items, *, next_page=None):
    return {"items": items, "next_page_params": next_page}


class FakeCostTransport:
    def __init__(self, address, target_history=None, transactions=None):
        self.address = address
        self.target_history = target_history
        self.transactions = transactions or {}
        self.calls = []

    def fetch_address(self, address):
        self.calls.append(("address", address))
        return self.address

    def fetch_address_token_transfers(self, scope, address):
        self.calls.append(("history", address))
        return self.target_history

    def fetch_transaction_token_transfers(self, tx_hash):
        self.calls.append(("tx", tx_hash))
        return self.transactions[tx_hash]


class FakeTransport:
    def __init__(self, token, holders):
        self.token = token
        self.holders = holders
        self.calls = []

    def fetch_token(self, scope):
        self.calls.append(("token", scope.contract_address))
        return self.token

    def fetch_holders(self, scope):
        self.calls.append(("holders", scope.contract_address))
        return self.holders


class HolderTests(unittest.TestCase):
    def setUp(self):
        self.scope = HolderScope(SYMBOL, 1_000, "ethereum", CONTRACT)

    def test_balance_desc_top10_is_decimal_address_level_evidence(self):
        values = [200000, 150000, 100000, 80000, 70000, 60000, 50000, 40000, 30000, 20000, 10000, 5000]
        snapshot = parse_blockscout_holder_snapshot(
            self.scope,
            token_payload(),
            holder_payload(values, next_page={"value": "5000"}),
        )
        self.assertEqual(snapshot.top10_holding_pct, Decimal("80"))
        self.assertEqual(len(snapshot.top_holders), 10)
        self.assertEqual(snapshot.coverage["contract"], HOLDER_CONTRACT)
        self.assertEqual(snapshot.coverage["identity_scope"], "direct_token_balance_address")
        self.assertEqual(snapshot.coverage["beneficial_owner_aggregation"], "not_available")
        self.assertFalse(snapshot.coverage["custody_pool_vault_collapse"])
        chip = dealer_chip(snapshot)
        self.assertEqual(chip["top10_holding_pct"], Decimal("80"))
        self.assertEqual(chip["top10_address_count"], 10)

    def test_current_blockscout_v2_token_shape_uses_address_hash_and_holders_count(self):
        token = token_payload(holders="12", total_supply="1000")
        token["address_hash"] = token.pop("address")
        token["holders_count"] = token.pop("holders")
        snapshot = parse_blockscout_holder_snapshot(
            self.scope,
            token,
            holder_payload([100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 9, 8],
                           next_page={"value": "8", "address_hash": "0x" + "12" * 20}),
        )
        self.assertEqual(snapshot.holder_count, 12)
        self.assertEqual(snapshot.top10_holding_pct, Decimal("55"))

    def test_less_than_ten_is_complete_only_when_holder_set_ends(self):
        snapshot = parse_blockscout_holder_snapshot(
            self.scope,
            token_payload(holders="3", total_supply="100"),
            holder_payload([50, 30, 20], next_page=None),
        )
        self.assertEqual(snapshot.top10_holding_pct, Decimal("100"))
        self.assertEqual(len(snapshot.top_holders), 3)
        with self.assertRaisesRegex(MarketCollectionError, "incomplete_top10_page"):
            parse_blockscout_holder_snapshot(
                self.scope,
                token_payload(holders="12", total_supply="100"),
                holder_payload([50, 30, 10], next_page={"value": "10"}),
            )

    def test_scope_order_duplicate_and_supply_inconsistency_fail_closed(self):
        bad_scope = dict(token_payload())
        bad_scope["address"] = "0x" + "11" * 20
        with self.assertRaisesRegex(MarketCollectionError, "scope_mismatch"):
            parse_blockscout_holder_snapshot(self.scope, bad_scope, holder_payload(range(20, 8, -1)))
        with self.assertRaisesRegex(MarketCollectionError, "holder_order_not_balance_desc"):
            parse_blockscout_holder_snapshot(
                self.scope, token_payload(total_supply="1000"),
                holder_payload([200, 190, 180, 170, 160, 150, 140, 130, 120, 121]),
            )
        duplicate = holder_payload(range(20, 8, -1))
        duplicate["items"][1]["address"] = duplicate["items"][0]["address"]
        with self.assertRaisesRegex(MarketCollectionError, "duplicate_holder_address"):
            parse_blockscout_holder_snapshot(self.scope, token_payload(), duplicate)
        with self.assertRaisesRegex(MarketCollectionError, "holder_supply_inconsistent"):
            parse_blockscout_holder_snapshot(
                self.scope, token_payload(total_supply="100"), holder_payload([20] * 10)
            )

    def test_collector_uses_explicit_transport_contract(self):
        transport = FakeTransport(
            token_payload(holders="10", total_supply="1000"),
            holder_payload([100, 90, 80, 70, 60, 50, 40, 30, 20, 10]),
        )
        snapshot = collect_blockscout_holder_snapshot(self.scope, transport)
        self.assertEqual(snapshot.top10_holding_pct, Decimal("55"))
        self.assertEqual([name for name, _ in transport.calls], ["token", "holders"])

    def test_direct_eoa_cost_reference_requires_complete_same_tx_quote_counterflow(self):
        holder = HolderAddress(EOA, Decimal("30000000000000000000"))
        target_history = history([
            transfer(token=CONTRACT, decimals=18, value="10000000000000000000",
                     from_address="0x" + "01" * 20, to_address=EOA, tx_hash=TX1),
            transfer(token=CONTRACT, decimals=18, value="20000000000000000000",
                     from_address="0x" + "02" * 20, to_address=EOA, tx_hash=TX2),
        ])
        transactions = {
            TX1: history([
                transfer(token=CONTRACT, decimals=18, value="10000000000000000000",
                         from_address="0x" + "01" * 20, to_address=EOA, tx_hash=TX1),
                transfer(token=USDT, decimals=6, value="20000000",
                         from_address=EOA, to_address="0x" + "03" * 20, tx_hash=TX1),
            ]),
            TX2: history([
                transfer(token=CONTRACT, decimals=18, value="20000000000000000000",
                         from_address="0x" + "02" * 20, to_address=EOA, tx_hash=TX2),
                transfer(token=USDT, decimals=6, value="40000000",
                         from_address=EOA, to_address="0x" + "04" * 20, tx_hash=TX2),
            ]),
        }
        reference = parse_blockscout_address_cost_reference(
            self.scope,
            holder,
            {"hash": EOA, "is_contract": False},
            target_history,
            transactions,
        )
        self.assertEqual(reference.status, "AVAILABLE")
        self.assertEqual(reference.cost_per_token, Decimal("2"))
        self.assertEqual(reference.quote_currency, "USDT")
        self.assertEqual(reference.covered_balance_raw, holder.balance_raw)
        self.assertEqual(reference.acquisition_tx_count, 2)
        self.assertEqual(reference.coverage["contract"], HOLDER_COST_CONTRACT)
        self.assertEqual(reference.coverage["beneficial_owner_aggregation"], "not_available")
        self.assertEqual(reference.coverage["yaozi_equivalence_status"],
                         "not_claimed_private_formula_unpublished")

    def test_cost_reference_fails_closed_on_contract_pagination_outflow_or_unpriced_inbound(self):
        holder = HolderAddress(EOA, Decimal("10000000000000000000"))
        contract_ref = parse_blockscout_address_cost_reference(
            self.scope, holder, {"hash": EOA, "is_contract": True}, None, {})
        self.assertEqual(contract_ref.status, "MISSING_DATA")
        self.assertEqual(contract_ref.missing_reason, "contract_holder_not_cost_attributable")

        paged = parse_blockscout_address_cost_reference(
            self.scope, holder, {"hash": EOA, "is_contract": False},
            history([], next_page={"block_number": 1}), {})
        self.assertEqual(paged.missing_reason, "address_history_not_complete_bounded_page")

        outbound = parse_blockscout_address_cost_reference(
            self.scope, holder, {"hash": EOA, "is_contract": False},
            history([transfer(token=CONTRACT, decimals=18, value="1",
                              from_address=EOA, to_address="0x" + "05" * 20, tx_hash=TX1)]), {})
        self.assertEqual(outbound.missing_reason,
                         "target_outflow_requires_unpublished_inventory_policy")

        inbound_history = history([
            transfer(token=CONTRACT, decimals=18, value="10000000000000000000",
                     from_address="0x" + "06" * 20, to_address=EOA, tx_hash=TX1),
        ])
        unpriced = parse_blockscout_address_cost_reference(
            self.scope, holder, {"hash": EOA, "is_contract": False}, inbound_history,
            {TX1: history([
                transfer(token=CONTRACT, decimals=18, value="10000000000000000000",
                         from_address="0x" + "06" * 20, to_address=EOA, tx_hash=TX1),
            ])})
        self.assertEqual(unpriced.missing_reason, "same_tx_quote_counterflow_not_unique")

    def test_cost_collector_stops_at_contract_holder_without_fetching_transfer_history(self):
        holder = HolderAddress(EOA, Decimal("10"))
        transport = FakeCostTransport({"hash": EOA, "is_contract": True})
        reference = collect_blockscout_address_cost_reference(self.scope, holder, transport)
        self.assertEqual(reference.status, "MISSING_DATA")
        self.assertEqual(reference.missing_reason, "contract_holder_not_cost_attributable")
        self.assertEqual(transport.calls, [("address", EOA)])


if __name__ == "__main__":
    unittest.main()
