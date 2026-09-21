"""Public address-level ERC-20 holder concentration facts.

Blockscout exposes token holders ordered by balance.  This module intentionally
stops at direct on-chain addresses: contracts, custodians, pools and vaults are
not collapsed into beneficial owners, and the resulting concentration is not
claimed to reproduce YAOZI's private holder reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import http.client
import json
import re
import ssl

from catos import research
from catos.market_collectors import MarketCollectionError


BLOCKSCOUT_ETHEREUM_HOST = "eth.blockscout.com"
HOLDER_CONTRACT = "catos-blockscout-address-holder-v1"
HOLDER_COST_CONTRACT = "catos-direct-address-stablecoin-cost-v1"
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_TOKEN_PATH_RE = re.compile(r"^/api/v2/tokens/0x[0-9a-f]{40}(?:/holders)?$")
_ADDRESS_PATH_RE = re.compile(r"^/api/v2/addresses/0x[0-9a-f]{40}$")
_ADDRESS_TOKEN_TRANSFERS_PATH_RE = re.compile(
    r"^/api/v2/addresses/0x[0-9a-f]{40}/token-transfers\?token=0x[0-9a-f]{40}$"
)
_TX_TOKEN_TRANSFERS_PATH_RE = re.compile(
    r"^/api/v2/transactions/0x[0-9a-f]{64}/token-transfers$"
)
_QUOTE_TOKENS = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
}


def _symbol(value):
    if type(value) is not str or not value.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    base = value.removesuffix("-USDT-SWAP")
    if not base or not base.isascii() or not base.isalnum():
        raise ValueError("invalid_symbol")
    return value


def _address(value):
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise ValueError("invalid_contract_address")
    return value.lower()


def _raw_integer(value, *, allow_zero=False):
    if type(value) is not str or not value.isascii() or not value.isdigit():
        raise MarketCollectionError("malformed_response")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise MarketCollectionError("malformed_response") from None
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise MarketCollectionError("malformed_response")
    return result


def _count(value):
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and value.isascii() and value.isdigit():
        return int(value)
    raise MarketCollectionError("malformed_response")


@dataclass(frozen=True, slots=True)
class HolderScope:
    symbol: str
    observed_at_ms: int
    chain: str
    contract_address: str

    def __post_init__(self):
        _symbol(self.symbol)
        if type(self.observed_at_ms) is not int or self.observed_at_ms < 0:
            raise ValueError("invalid_observed_at_ms")
        if self.chain != "ethereum":
            raise ValueError("unsupported_holder_chain")
        _address(self.contract_address)


@dataclass(frozen=True, slots=True)
class HolderAddress:
    address: str
    balance_raw: Decimal


@dataclass(frozen=True, slots=True)
class HolderSnapshot:
    symbol: str
    observed_at_ms: int
    chain: str
    contract_address: str
    source: str
    total_supply_raw: Decimal
    holder_count: int | None
    top_holders: tuple[HolderAddress, ...]
    top10_holding_pct: Decimal
    coverage: dict


@dataclass(frozen=True, slots=True)
class AddressCostReference:
    """Strict direct-address acquisition reference; never a beneficial-owner cost."""

    symbol: str
    observed_at_ms: int
    chain: str
    contract_address: str
    holder_address: str
    status: str
    cost_per_token: Decimal | None
    quote_currency: str | None
    covered_balance_raw: Decimal
    acquisition_tx_count: int
    missing_reason: str | None
    coverage: dict


class BlockscoutEthereumHolderTransport:
    """Keyless fixed-host GET adapter for the public Ethereum Blockscout instance."""

    def __init__(self, *, timeout_ms=8_000, max_body_bytes=1_000_000):
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30_000:
            raise ValueError("invalid_timeout")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 2_000_000:
            raise ValueError("invalid_body_limit")
        self.timeout_ms = timeout_ms
        self.max_body_bytes = max_body_bytes

    def _get(self, path):
        if type(path) is not str or not any(pattern.fullmatch(path) for pattern in (
            _TOKEN_PATH_RE,
            _ADDRESS_PATH_RE,
            _ADDRESS_TOKEN_TRANSFERS_PATH_RE,
            _TX_TOKEN_TRANSFERS_PATH_RE,
        )):
            raise MarketCollectionError("source_not_allowed")
        connection = http.client.HTTPSConnection(
            BLOCKSCOUT_ETHEREUM_HOST,
            port=443,
            timeout=self.timeout_ms / 1000,
            context=ssl.create_default_context(),
        )
        response = None
        try:
            connection.request(
                "GET", path, body=None,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "catOS-public-holders/1.0",
                },
            )
            response = connection.getresponse()
            payload = response.read(self.max_body_bytes + 1)
            if response.status != 200:
                raise MarketCollectionError(f"source_http_{response.status}")
            if len(payload) > self.max_body_bytes:
                raise MarketCollectionError("source_body_too_large")
            try:
                return json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise MarketCollectionError("malformed_response") from None
        finally:
            if response is not None:
                response.close()
            connection.close()

    def fetch_token(self, scope: HolderScope):
        if not isinstance(scope, HolderScope):
            raise ValueError("invalid_holder_scope")
        return self._get(f"/api/v2/tokens/{scope.contract_address.lower()}")

    def fetch_holders(self, scope: HolderScope):
        if not isinstance(scope, HolderScope):
            raise ValueError("invalid_holder_scope")
        return self._get(f"/api/v2/tokens/{scope.contract_address.lower()}/holders")

    def fetch_address(self, address):
        return self._get(f"/api/v2/addresses/{_address(address)}")

    def fetch_address_token_transfers(self, scope: HolderScope, address):
        if not isinstance(scope, HolderScope):
            raise ValueError("invalid_holder_scope")
        return self._get(
            f"/api/v2/addresses/{_address(address)}/token-transfers"
            f"?token={scope.contract_address.lower()}"
        )

    def fetch_transaction_token_transfers(self, transaction_hash):
        if type(transaction_hash) is not str or _TX_HASH_RE.fullmatch(transaction_hash) is None:
            raise ValueError("invalid_transaction_hash")
        return self._get(
            f"/api/v2/transactions/{transaction_hash.lower()}/token-transfers"
        )


def _holder_address(value):
    if type(value) is dict:
        value = value.get("hash")
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise MarketCollectionError("malformed_response")
    return value.lower()


def _transaction_hash(value):
    if type(value) is not str or _TX_HASH_RE.fullmatch(value) is None:
        raise MarketCollectionError("malformed_response")
    return value.lower()


def _token_identity(value):
    if type(value) is not dict:
        raise MarketCollectionError("malformed_response")
    address = value.get("address_hash", value.get("address"))
    if type(address) is not str or _ADDRESS_RE.fullmatch(address) is None:
        raise MarketCollectionError("malformed_response")
    return address.lower()


def _token_amount(item):
    total = item.get("total") if type(item) is dict else None
    if type(total) is not dict:
        raise MarketCollectionError("malformed_response")
    raw = _raw_integer(total.get("value"), allow_zero=False)
    decimals = total.get("decimals")
    if type(decimals) is not str or not decimals.isascii() or not decimals.isdigit():
        raise MarketCollectionError("malformed_response")
    decimals = int(decimals)
    if not 0 <= decimals <= 36:
        raise MarketCollectionError("malformed_response")
    return raw, decimals


def _cost_missing(scope, holder, reason, *, address_kind, acquisition_tx_count=0):
    return AddressCostReference(
        symbol=scope.symbol,
        observed_at_ms=scope.observed_at_ms,
        chain=scope.chain,
        contract_address=scope.contract_address.lower(),
        holder_address=holder.address,
        status="MISSING_DATA",
        cost_per_token=None,
        quote_currency=None,
        covered_balance_raw=Decimal("0"),
        acquisition_tx_count=acquisition_tx_count,
        missing_reason=reason,
        coverage={
            "contract": HOLDER_COST_CONTRACT,
            "identity_scope": "direct_token_balance_address",
            "address_kind": address_kind,
            "beneficial_owner_aggregation": "not_available",
            "requires_complete_address_history": True,
            "requires_same_tx_quote_counterflow": True,
            "allowed_quote_assets": ["USDT", "USDC"],
            "outflow_inventory_policy": "not_inferred",
            "yaozi_equivalence_status": "not_claimed_private_formula_unpublished",
            "observation_only": True,
            "smf_eligible": False,
        },
    )


def parse_blockscout_address_cost_reference(
        scope: HolderScope, holder: HolderAddress, address_payload,
        target_history_payload, transaction_payloads):
    """Derive a narrow same-transaction quote-spend cost reference.

    The reference is available only for a direct EOA whose complete target-token
    history fits the bounded source page, has no target-token outflow, and whose
    entire current balance is explained by transactions that also contain a
    direct USDT or USDC net spend by that same address. This deliberately avoids
    inventing transfer cost, disposal inventory rules, custody ownership, or the
    private YAOZI main-cost formula.
    """
    if not isinstance(scope, HolderScope) or not isinstance(holder, HolderAddress):
        raise ValueError("invalid_holder_cost_scope")
    if type(address_payload) is not dict:
        raise MarketCollectionError("malformed_response")
    address_hash = address_payload.get("hash")
    if type(address_hash) is not str or address_hash.lower() != holder.address:
        raise MarketCollectionError("scope_mismatch")
    is_contract = address_payload.get("is_contract")
    if type(is_contract) is not bool:
        raise MarketCollectionError("malformed_response")
    if is_contract:
        return _cost_missing(
            scope, holder, "contract_holder_not_cost_attributable", address_kind="contract")

    if type(target_history_payload) is not dict or type(transaction_payloads) is not dict:
        raise MarketCollectionError("malformed_response")
    items = target_history_payload.get("items")
    if type(items) is not list:
        raise MarketCollectionError("malformed_response")
    if target_history_payload.get("next_page_params") is not None:
        return _cost_missing(
            scope, holder, "address_history_not_complete_bounded_page", address_kind="eoa")

    inbound_transactions = []
    seen_transactions = set()
    for item in items:
        if type(item) is not dict or _token_identity(item.get("token")) != scope.contract_address.lower():
            raise MarketCollectionError("scope_mismatch")
        _token_amount(item)
        from_address = _holder_address(item.get("from"))
        to_address = _holder_address(item.get("to"))
        if from_address == holder.address and to_address != holder.address:
            return _cost_missing(
                scope, holder, "target_outflow_requires_unpublished_inventory_policy",
                address_kind="eoa")
        if to_address == holder.address and from_address != holder.address:
            tx_hash = _transaction_hash(item.get("transaction_hash"))
            if tx_hash not in seen_transactions:
                seen_transactions.add(tx_hash)
                inbound_transactions.append(tx_hash)
        elif from_address != holder.address and to_address != holder.address:
            raise MarketCollectionError("scope_mismatch")

    if not inbound_transactions:
        return _cost_missing(scope, holder, "no_inbound_target_history", address_kind="eoa")

    target_decimals = None
    quote_contract = None
    quote_currency = None
    covered_raw = Decimal("0")
    quote_spend_units = Decimal("0")
    for tx_hash in inbound_transactions:
        tx_payload = transaction_payloads.get(tx_hash)
        if type(tx_payload) is not dict:
            return _cost_missing(
                scope, holder, "transaction_detail_missing", address_kind="eoa",
                acquisition_tx_count=len(inbound_transactions))
        tx_items = tx_payload.get("items")
        if type(tx_items) is not list:
            raise MarketCollectionError("malformed_response")
        if tx_payload.get("next_page_params") is not None:
            return _cost_missing(
                scope, holder, "transaction_transfer_page_incomplete", address_kind="eoa",
                acquisition_tx_count=len(inbound_transactions))

        target_in = Decimal("0")
        target_out = Decimal("0")
        quote_nets = {}
        for transfer in tx_items:
            if type(transfer) is not dict:
                raise MarketCollectionError("malformed_response")
            transfer_hash = _transaction_hash(transfer.get("transaction_hash"))
            if transfer_hash != tx_hash:
                raise MarketCollectionError("scope_mismatch")
            token_address = _token_identity(transfer.get("token"))
            raw, decimals = _token_amount(transfer)
            from_address = _holder_address(transfer.get("from"))
            to_address = _holder_address(transfer.get("to"))
            if token_address == scope.contract_address.lower():
                if target_decimals is None:
                    target_decimals = decimals
                elif target_decimals != decimals:
                    raise MarketCollectionError("scope_mismatch")
                if to_address == holder.address and from_address != holder.address:
                    target_in += raw
                if from_address == holder.address and to_address != holder.address:
                    target_out += raw
            quote = _QUOTE_TOKENS.get(token_address)
            if quote is not None:
                symbol, expected_decimals = quote
                if decimals != expected_decimals:
                    raise MarketCollectionError("scope_mismatch")
                signed_raw = Decimal("0")
                if from_address == holder.address and to_address != holder.address:
                    signed_raw += raw
                if to_address == holder.address and from_address != holder.address:
                    signed_raw -= raw
                if signed_raw:
                    quote_nets[token_address] = quote_nets.get(token_address, Decimal("0")) + signed_raw

        if target_in <= target_out or target_out != 0:
            return _cost_missing(
                scope, holder, "target_transaction_not_pure_inbound", address_kind="eoa",
                acquisition_tx_count=len(inbound_transactions))
        positive_quote_spends = [
            (contract, amount) for contract, amount in quote_nets.items() if amount > 0
        ]
        if len(positive_quote_spends) != 1:
            return _cost_missing(
                scope, holder, "same_tx_quote_counterflow_not_unique", address_kind="eoa",
                acquisition_tx_count=len(inbound_transactions))
        current_quote_contract, quote_raw = positive_quote_spends[0]
        current_quote_currency, quote_decimals = _QUOTE_TOKENS[current_quote_contract]
        if quote_contract is None:
            quote_contract = current_quote_contract
            quote_currency = current_quote_currency
        elif quote_contract != current_quote_contract:
            return _cost_missing(
                scope, holder, "mixed_quote_currency", address_kind="eoa",
                acquisition_tx_count=len(inbound_transactions))
        covered_raw += target_in
        with localcontext(research._CONTEXT):
            quote_spend_units += quote_raw / (Decimal("10") ** quote_decimals)

    if target_decimals is None:
        raise MarketCollectionError("malformed_response")
    if covered_raw != holder.balance_raw:
        return _cost_missing(
            scope, holder, "current_balance_not_fully_explained_by_acquisitions",
            address_kind="eoa", acquisition_tx_count=len(inbound_transactions))
    with localcontext(research._CONTEXT):
        token_units = covered_raw / (Decimal("10") ** target_decimals)
        cost = quote_spend_units / token_units
    return AddressCostReference(
        symbol=scope.symbol,
        observed_at_ms=scope.observed_at_ms,
        chain=scope.chain,
        contract_address=scope.contract_address.lower(),
        holder_address=holder.address,
        status="AVAILABLE",
        cost_per_token=cost,
        quote_currency=quote_currency,
        covered_balance_raw=covered_raw,
        acquisition_tx_count=len(inbound_transactions),
        missing_reason=None,
        coverage={
            "contract": HOLDER_COST_CONTRACT,
            "identity_scope": "direct_token_balance_address",
            "address_kind": "eoa",
            "beneficial_owner_aggregation": "not_available",
            "address_history_complete": True,
            "current_balance_fully_explained": True,
            "quote_contract": quote_contract,
            "quote_currency": quote_currency,
            "quote_semantics": "same_transaction_direct_net_spend",
            "outflow_inventory_policy": "not_needed_no_target_outflow",
            "yaozi_equivalence_status": "not_claimed_private_formula_unpublished",
            "observation_only": True,
            "smf_eligible": False,
        },
    )


def collect_blockscout_address_cost_reference(scope: HolderScope, holder: HolderAddress, transport):
    required = (
        "fetch_address", "fetch_address_token_transfers", "fetch_transaction_token_transfers")
    if not isinstance(scope, HolderScope) or not isinstance(holder, HolderAddress):
        raise ValueError("invalid_holder_cost_scope")
    if any(not callable(getattr(transport, name, None)) for name in required):
        raise ValueError("invalid_holder_cost_transport")
    address_payload = transport.fetch_address(holder.address)
    if type(address_payload) is dict and address_payload.get("is_contract") is True:
        return parse_blockscout_address_cost_reference(
            scope, holder, address_payload, None, {})
    history = transport.fetch_address_token_transfers(scope, holder.address)
    if type(history) is not dict:
        raise MarketCollectionError("malformed_response")
    if history.get("next_page_params") is not None:
        return parse_blockscout_address_cost_reference(scope, holder, address_payload, history, {})
    tx_hashes = []
    seen = set()
    items = history.get("items")
    if type(items) is not list:
        raise MarketCollectionError("malformed_response")
    for item in items:
        if type(item) is not dict:
            raise MarketCollectionError("malformed_response")
        from_address = _holder_address(item.get("from"))
        to_address = _holder_address(item.get("to"))
        if from_address == holder.address and to_address != holder.address:
            return parse_blockscout_address_cost_reference(
                scope, holder, address_payload, history, {})
        if to_address == holder.address and from_address != holder.address:
            tx_hash = _transaction_hash(item.get("transaction_hash"))
            if tx_hash not in seen:
                seen.add(tx_hash)
                tx_hashes.append(tx_hash)
    transaction_payloads = {
        tx_hash: transport.fetch_transaction_token_transfers(tx_hash)
        for tx_hash in tx_hashes
    }
    return parse_blockscout_address_cost_reference(
        scope, holder, address_payload, history, transaction_payloads)


def parse_blockscout_holder_snapshot(scope: HolderScope, token_payload, holders_payload):
    """Parse one balance-desc first page into a proven top-10 address share."""
    if not isinstance(scope, HolderScope):
        raise ValueError("invalid_holder_scope")
    if type(token_payload) is not dict or type(holders_payload) is not dict:
        raise MarketCollectionError("malformed_response")

    token_address = token_payload.get("address_hash", token_payload.get("address"))
    if type(token_address) is not str or token_address.lower() != scope.contract_address.lower():
        raise MarketCollectionError("scope_mismatch")
    if token_payload.get("type") != "ERC-20":
        raise MarketCollectionError("unsupported_token_type")
    total_supply = _raw_integer(token_payload.get("total_supply"))
    holder_count = _count(token_payload.get("holders_count", token_payload.get("holders")))

    items = holders_payload.get("items")
    if type(items) is not list:
        raise MarketCollectionError("malformed_response")
    next_page = holders_payload.get("next_page_params")
    if len(items) < 10 and next_page is not None and (holder_count is None or holder_count > len(items)):
        raise MarketCollectionError("incomplete_top10_page")
    if holder_count is not None and holder_count > len(items) and len(items) < 10:
        raise MarketCollectionError("incomplete_top10_page")

    parsed = []
    seen = set()
    previous = None
    for item in items[:10]:
        if type(item) is not dict:
            raise MarketCollectionError("malformed_response")
        address = _holder_address(item.get("address"))
        balance = _raw_integer(item.get("value"), allow_zero=False)
        if address in seen:
            raise MarketCollectionError("duplicate_holder_address")
        if previous is not None and balance > previous:
            raise MarketCollectionError("holder_order_not_balance_desc")
        seen.add(address)
        previous = balance
        parsed.append(HolderAddress(address, balance))

    expected = 10 if holder_count is None or holder_count >= 10 else holder_count
    if len(parsed) < expected:
        raise MarketCollectionError("incomplete_top10_page")
    if not parsed:
        raise MarketCollectionError("empty_holder_set")

    with localcontext(research._CONTEXT):
        held = sum((row.balance_raw for row in parsed), Decimal("0"))
        share = held / total_supply * Decimal("100")
    if share > Decimal("100"):
        raise MarketCollectionError("holder_supply_inconsistent")

    return HolderSnapshot(
        symbol=scope.symbol,
        observed_at_ms=scope.observed_at_ms,
        chain=scope.chain,
        contract_address=scope.contract_address.lower(),
        source="blockscout-ethereum-v2-token-holders",
        total_supply_raw=total_supply,
        holder_count=holder_count,
        top_holders=tuple(parsed),
        top10_holding_pct=share,
        coverage={
            "contract": HOLDER_CONTRACT,
            "ordering_contract": "blockscout_v2_balance_desc",
            "top10_complete": True,
            "identity_scope": "direct_token_balance_address",
            "beneficial_owner_aggregation": "not_available",
            "custody_pool_vault_collapse": False,
            "yaozi_equivalence_status": "not_claimed_source_semantics_only",
            "observation_only": True,
            "smf_eligible": False,
        },
    )


def collect_blockscout_holder_snapshot(scope: HolderScope, transport):
    if not isinstance(scope, HolderScope):
        raise ValueError("invalid_holder_scope")
    if not callable(getattr(transport, "fetch_token", None)) or not callable(getattr(transport, "fetch_holders", None)):
        raise ValueError("invalid_holder_transport")
    return parse_blockscout_holder_snapshot(
        scope,
        transport.fetch_token(scope),
        transport.fetch_holders(scope),
    )


def dealer_chip(snapshot: HolderSnapshot):
    if not isinstance(snapshot, HolderSnapshot):
        raise ValueError("invalid_holder_snapshot")
    return {
        "top10_holding_pct": snapshot.top10_holding_pct,
        "top10_address_count": len(snapshot.top_holders),
        "holder_count": snapshot.holder_count,
        "source": snapshot.source,
        "chain": snapshot.chain,
        "contract_address": snapshot.contract_address,
        "coverage": snapshot.coverage,
        "top10_addresses": [row.address for row in snapshot.top_holders],
    }
