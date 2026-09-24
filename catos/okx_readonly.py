"""I-a offline OKX evidence checks. No transport, credentials, writer or trade gate.

Caller-supplied coverage assertions are fixture metadata, not exchange guarantees.
Raw payloads and evidence must remain available to the future Supervisor adapter.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from collections.abc import Mapping
from types import MappingProxyType
import hashlib
import json

from catos import ipc, research


def number(row, field):
    return ipc.decimal_text(row.get(field), field, derived=True)


def text(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {field}")
    return value


def rows(payload):
    if payload.get("code") != "0" or not isinstance(payload.get("data"), list):
        raise ValueError("unsuccessful or malformed response")
    if len(payload["data"]) > 1000 or any(not isinstance(r, dict) for r in payload["data"]):
        raise ValueError("invalid offline response rows")
    return payload["data"]


@dataclass(frozen=True)
class Evidence:
    account: str
    environment: str
    source: str
    evidence_id: str
    source_ms: int
    received_ms: int
    complete: bool

    def __post_init__(self):
        for field in ("account", "environment", "source", "evidence_id"):
            text(vars(self), field)
        for field in ("source_ms", "received_ms"):
            ipc.integer(getattr(self, field), field)
        if type(self.complete) is not bool:
            raise ValueError("complete must be explicit bool")


@dataclass(frozen=True)
class FlowClassificationEntry:
    bill_type: str
    sub_type: str
    category: str
    evidence: str

    def __post_init__(self):
        for name in ("bill_type", "sub_type", "evidence"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value.strip() != value:
                raise ValueError("invalid flow classification entry")
        if self.category not in ("external", "internal", "forbidden"):
            raise ValueError("invalid flow classification category")


@dataclass(frozen=True)
class FlowClassification:
    name: str
    entries: tuple[FlowClassificationEntry, ...]
    complete: bool = False

    def __post_init__(self):
        if (not isinstance(self.name, str) or not self.name
                or self.name.strip() != self.name):
            raise ValueError("invalid flow classification id")
        if type(self.entries) is not tuple or any(
                not isinstance(entry, FlowClassificationEntry) for entry in self.entries):
            raise ValueError("invalid flow classification entries")
        if type(self.complete) is not bool:
            raise ValueError("flow classification completeness must be explicit bool")
        keys = [(entry.bill_type, entry.sub_type) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate flow classification entry")

    @property
    def classification_id(self):
        payload = {
            "complete": self.complete,
            "entries": [
                (entry.bill_type, entry.sub_type, entry.category, entry.evidence)
                for entry in sorted(
                    self.entries,
                    key=lambda entry: (entry.bill_type, entry.sub_type, entry.category, entry.evidence),
                )
            ],
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.name}:{digest}"

    def mapping(self):
        return MappingProxyType({
            (entry.bill_type, entry.sub_type): entry.category for entry in self.entries
        })


OKX_STATIC_TRANSFER_FLOW_CLASSIFICATION = FlowClassification(
    "okx-v5-static-transfer-2026-09-21",
    (
        FlowClassificationEntry(
            "1", "11", "external",
            "OKX API v5 Get bill types example: type 1 Transfer, subType 11 Transfer in",
        ),
        FlowClassificationEntry(
            "1", "12", "external",
            "OKX API v5 Get bill types example: type 1 Transfer, subType 12 Transfer out",
        ),
    ),
)


OKX_DEMO_CATALOG_FLOW_CLASSIFICATION = FlowClassification(
    "okx-demo-subtypes-2026-09-22",
    tuple(
        FlowClassificationEntry(
            bill_type, sub_type, category,
            "GET /api/v5/account/subtypes; received_ms=1790039748822; "
            "catalog_sha256=84373423204fe2ccf65955ba096e11687e96879caf436d00efcf5af030506e4c; "
            + label + "; " + rationale,
        )
        for bill_type, sub_type, category, label, rationale in (
            ("1", "283", "forbidden", "Transfer / Asset transfer for spot copy trading", "C1-B: copy trading is unsupported in the dedicated catOS account"),
            ("1", "284", "forbidden", "Transfer / Copy trade automatic transfer in", "C1-B: copy trading is unsupported in the dedicated catOS account"),
            ("1", "285", "forbidden", "Transfer / Copy trade manual transfer in", "C1-B: copy trading is unsupported in the dedicated catOS account"),
            ("1", "286", "forbidden", "Transfer / Copy trade automatic transfer out", "C1-B: copy trading is unsupported in the dedicated catOS account"),
            ("1", "287", "forbidden", "Transfer / Copy trade manual transfer out", "C1-B: copy trading is unsupported in the dedicated catOS account"),
            ("12", "200", "forbidden", "Strategy transfer / From trading bot", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "201", "forbidden", "Strategy transfer / From trading bot (manual)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "202", "forbidden", "Strategy transfer / To trading bot", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "203", "forbidden", "Strategy transfer / To trading bot (manual)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "267", "forbidden", "Strategy transfer / Profit share payment", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "268", "forbidden", "Strategy transfer / Profit share refund", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "269", "forbidden", "Strategy transfer / Profit share income", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "372", "forbidden", "Strategy transfer / Bot airdrop (transfer in)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "373", "forbidden", "Strategy transfer / Bot airdrop (transfer out)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "374", "forbidden", "Strategy transfer / Bot airdrop reclaim (transfer in)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("12", "375", "forbidden", "Strategy transfer / Bot airdrop reclaim (transfer out)", "C1-B: exchange trading bot and associated profit-share/airdrop activity is unsupported"),
            ("26", "296", "forbidden", " / From structured order placements", "C1-B: structured product activity is unsupported"),
            ("26", "297", "forbidden", " / To structured order placements", "C1-B: structured product activity is unsupported"),
            ("26", "298", "forbidden", " / From structured settlements", "C1-B: structured product activity is unsupported"),
            ("26", "299", "forbidden", " / To structured settlements", "C1-B: structured product activity is unsupported"),
            ("26", "340", "forbidden", " / Flywheel subscription (in)", "C1-B: structured product activity is unsupported"),
            ("26", "341", "forbidden", " / Flywheel subscription (out)", "C1-B: structured product activity is unsupported"),
            ("26", "342", "forbidden", " / Flywheel settlement (in)", "C1-B: structured product activity is unsupported"),
            ("26", "343", "forbidden", " / Flywheel settlement (out)", "C1-B: structured product activity is unsupported"),
            ("26", "344", "forbidden", " / Flywheel failed trade (in)", "C1-B: structured product activity is unsupported"),
            ("26", "345", "forbidden", " / Flywheel failed trade (out)", "C1-B: structured product activity is unsupported"),
            ("32", "324", "forbidden", "Move position / Buy", "C1-B: Move position activity is unsupported"),
            ("32", "325", "forbidden", "Move position / Sell", "C1-B: Move position activity is unsupported"),
            ("32", "326", "forbidden", "Move position / Open long", "C1-B: Move position activity is unsupported"),
            ("32", "327", "forbidden", "Move position / Open short", "C1-B: Move position activity is unsupported"),
            ("32", "328", "forbidden", "Move position / Close long", "C1-B: Move position activity is unsupported"),
            ("32", "329", "forbidden", "Move position / Close short", "C1-B: Move position activity is unsupported"),
            ("35", "382", "forbidden", "Options market / Simple options asset transfer out", "C1-B: options product transfers are unsupported"),
            ("35", "383", "forbidden", "Options market / Simple options asset transfer in", "C1-B: options product transfers are unsupported"),
            ("38", "416", "forbidden", "USDG Rewards / USDG subscription", "C1-B: USDG product subscription/redemption is unsupported"),
            ("38", "417", "forbidden", "USDG Rewards / USDG redemption", "C1-B: USDG product subscription/redemption is unsupported"),
            ("38", "418", "forbidden", "USDG Rewards / USDG redemption (principal)", "C1-B: USDG product subscription/redemption is unsupported"),
            ("38", "419", "forbidden", "USDG Rewards / USDG subscription (principal)", "C1-B: USDG product subscription/redemption is unsupported"),
            ("250", "250", "forbidden", "Profit share payment / Contract profit share payment", "C1-B: copy/profit-share activity is unsupported"),
            ("250", "280", "forbidden", "Profit share payment / Spot profit share payment", "C1-B: copy/profit-share activity is unsupported"),
            ("251", "251", "forbidden", "Profit share refund / Contract profit share refund", "C1-B: copy/profit-share activity is unsupported"),
            ("251", "281", "forbidden", "Profit share refund / Spot profit share refund", "C1-B: copy/profit-share activity is unsupported"),
            ("1", "420", "forbidden", "Transfer / VIP Loan delta reduction transfer in", "C1-B: OKX documents VIP Loan as a separate risk-unit/funding-account loan product outside the dedicated catOS USDT-M SWAP account scope"),
            ("6", "160", "forbidden", "Margin transfer / Manual margin increase", "C1-B: OKX documents manual margin adjustment for isolated MARGIN positions; catOS v1 is cross USDT-M SWAP only"),
            ("6", "161", "forbidden", "Margin transfer / Manual margin decrease", "C1-B: OKX documents manual margin adjustment for isolated MARGIN positions; catOS v1 is cross USDT-M SWAP only"),
            ("6", "162", "forbidden", "Margin transfer / Auto margin increase", "C1-B: OKX documents position margin adjustment under MARGIN modes; catOS v1 is cross USDT-M SWAP only"),
            ("15", "210", "forbidden", "Quick margin / Manual borrow", "C1-B: OKX documents Quick Margin as a MARGIN borrowing product; catOS v1 is USDT-M SWAP only"),
            ("15", "211", "forbidden", "Quick margin / Manual repay", "C1-B: OKX documents Quick Margin as a MARGIN borrowing product; catOS v1 is USDT-M SWAP only"),
            ("15", "212", "forbidden", "Quick margin / Auto borrow", "C1-B: OKX documents Quick Margin as a MARGIN borrowing product; catOS v1 is USDT-M SWAP only"),
            ("15", "213", "forbidden", "Quick margin / Auto repay", "C1-B: OKX documents Quick Margin as a MARGIN borrowing product; catOS v1 is USDT-M SWAP only"),
            ("15", "216", "forbidden", "Quick margin / Borrow to repay interest", "C1-B: OKX documents Quick Margin as a MARGIN borrowing product; catOS v1 is USDT-M SWAP only"),
            ("1", "257", "external", "Transfer / Using voucher", "C3-B: non-strategy positive credit excluded from strategy daily PnL"),
            ("1", "288", "external", "Transfer / Trading bonus transfer in", "C3-B: non-strategy positive credit excluded from strategy daily PnL"),
            ("1", "381", "external", "Transfer / Auto Earn+ lending interest", "C3-B: non-strategy positive credit excluded from strategy daily PnL"),
            ("1", "392", "external", "Transfer / Auto Earn+ staking reward", "C3-B: non-strategy positive credit excluded from strategy daily PnL"),
            ("1", "429", "external", "Transfer / Auto Earn+ Bonus", "C3-B: non-strategy positive credit excluded from strategy daily PnL"),
            ("7", "9", "internal", "Interest / Interest deduction", "C4-B: interest, fee, penalty and cost refund remain in equity PnL"),
            ("7", "14", "internal", "Interest / VIP Loan deduction", "C4-B: interest, fee, penalty and cost refund remain in equity PnL"),
            ("7", "293", "internal", "Interest / VIP Loan deduction", "C4-B: interest, fee, penalty and cost refund remain in equity PnL"),
            ("7", "294", "internal", "Interest / VIP Loan refund", "C4-B: interest, fee, penalty and cost refund remain in equity PnL"),
            ("7", "295", "internal", "Interest / VIP Loan overdue penalty", "C4-B: interest, fee, penalty and cost refund remain in equity PnL"),
            ("33", "348", "internal", "Loans / Forced repayment", "C2-A/C4-B: OKX forced-repayment documentation describes Trading Account assets being sold or converted to repay in-scope liabilities; this catalog row identifies no account-scope crossing"),
            ("33", "349", "internal", "Loans / Forced repayment", "C2-A/C4-B: OKX forced-repayment documentation describes Trading Account assets being sold or converted to repay in-scope liabilities; this catalog row identifies no account-scope crossing"),
            ("33", "350", "internal", "Loans / Forced repayment fee deduction", "C4-B: repayment fee, penalty and refund remain in equity PnL"),
            ("33", "351", "internal", "Loans / Forced repayment refund", "C4-B: repayment fee, penalty and refund remain in equity PnL"),
            ("33", "352", "internal", "Loans / Forced repayment penalty fee deduction", "C4-B: repayment fee, penalty and refund remain in equity PnL"),
            ("33", "353", "internal", "Loans / Forced repayment penalty fee (pending deduction)", "C4-B: repayment fee, penalty and refund remain in equity PnL"),
            ("33", "354", "internal", "Loans / Forced repayment penalty fee", "C4-B: repayment fee, penalty and refund remain in equity PnL"),
            ("33", "356", "internal", "Loans / Forced conversion (pending deduction)", "C2-A/C4-B: OKX auto-crypto-conversion documentation describes account assets being converted to reduce an in-scope liability; unlike 357-359, this catalog row does not identify a transfer across the verified Trading Account scope"),
            ("33", "357", "external", "Loans / Transfer of forced-converted asset to funding account", "C2-A/C4-B: the official catalog explicitly moves the asset from trading-account equity to the funding account; preserve signed balChg as an external scope crossing"),
            ("33", "358", "external", "Loans / OTC system account transfer in", "C2-A/C4-B: the official catalog explicitly identifies an OTC system-account transfer crossing the verified trading-account equity scope; preserve signed balChg"),
            ("33", "359", "external", "Loans / OTC system account transfer out", "C2-A/C4-B: the official catalog explicitly identifies an OTC system-account transfer crossing the verified trading-account equity scope; preserve signed balChg"),
            ("1", "11", "external", "Transfer / Transfer in", "Capital enters trading account"),
            ("1", "12", "external", "Transfer / Transfer out", "Capital leaves trading account"),
            ("2", "1", "internal", "Trade / Buy", "Trading activity already reflected in equity"),
            ("2", "2", "internal", "Trade / Sell", "Trading activity already reflected in equity"),
            ("2", "3", "internal", "Trade / Open long", "Trading activity already reflected in equity"),
            ("2", "4", "internal", "Trade / Open short", "Trading activity already reflected in equity"),
            ("2", "5", "internal", "Trade / Close long", "Trading activity already reflected in equity"),
            ("2", "6", "internal", "Trade / Close short", "Trading activity already reflected in equity"),
            ("2", "407", "internal", "Trade / Momentum catcher spot sell", "Trading activity already reflected in equity"),
            ("2", "408", "internal", "Trade / Momentum catcher spot buy", "Trading activity already reflected in equity"),
            ("2", "410", "internal", "Trade / Buy up", "Trading activity already reflected in equity"),
            ("2", "411", "internal", "Trade / Buy down", "Trading activity already reflected in equity"),
            ("2", "412", "internal", "Trade / Sell up", "Trading activity already reflected in equity"),
            ("2", "413", "internal", "Trade / Sell down", "Trading activity already reflected in equity"),
            ("3", "112", "internal", "Delivery / Expiry (close long)", "Contract expiry activity already reflected in equity"),
            ("3", "113", "internal", "Delivery / Expiry (close short)", "Contract expiry activity already reflected in equity"),
            ("3", "117", "internal", "Delivery / Overloss recovery (expiry)", "Expiry loss recovery already reflected in equity"),
            ("3", "170", "internal", "Delivery / Exercised", "Option exercise activity already reflected in equity"),
            ("3", "171", "internal", "Delivery / Exercised by counterparty", "Option exercise activity already reflected in equity"),
            ("3", "172", "internal", "Delivery / Expired OTM", "Option expiry activity already reflected in equity"),
            ("3", "414", "internal", "Delivery / Expiry up", "Contract expiry activity already reflected in equity"),
            ("3", "415", "internal", "Delivery / Expiry down", "Contract expiry activity already reflected in equity"),
            ("5", "100", "internal", "Forced liquidation / ADL close long", "Forced trading activity already reflected in equity"),
            ("5", "101", "internal", "Forced liquidation / ADL close short", "Forced trading activity already reflected in equity"),
            ("5", "102", "internal", "Forced liquidation / Partial liquidation buy", "Forced trading activity already reflected in equity"),
            ("5", "103", "internal", "Forced liquidation / Partial liquidation sell", "Forced trading activity already reflected in equity"),
            ("5", "104", "internal", "Forced liquidation / Liquidation (close long)", "Forced trading activity already reflected in equity"),
            ("5", "105", "internal", "Forced liquidation / Liquidation (close short)", "Forced trading activity already reflected in equity"),
            ("5", "106", "internal", "Forced liquidation / Liquidation buy", "Forced trading activity already reflected in equity"),
            ("5", "107", "internal", "Forced liquidation / Forced liquidation sell", "Forced trading activity already reflected in equity"),
            ("5", "110", "internal", "Forced liquidation / Liquidation transfer in", "Liquidation lifecycle activity already reflected in equity"),
            ("5", "111", "internal", "Forced liquidation / Liquidation transfer out", "Liquidation lifecycle activity already reflected in equity"),
            ("5", "116", "internal", "Forced liquidation / Balance deducted for liquidation", "Liquidation loss already reflected in equity"),
            ("5", "313", "internal", "Forced liquidation / Liquidation offset", "C4-B: liquidation offset is part of the forced-repayment/liquidation lifecycle already reflected in account equity"),
            ("5", "314", "internal", "Forced liquidation / Forced interest repayment", "C4-B: forced interest repayment is an account liability cost/repayment event already reflected in equity"),
            ("5", "315", "internal", "Forced liquidation / Delisting repayment", "C4-B: repayment triggered by delisting settles an account liability and remains in account equity"),
            ("5", "316", "internal", "Forced liquidation / Liquidation repayment", "C4-B: liquidation repayment is part of the forced-repayment lifecycle already reflected in account equity"),
            ("5", "317", "internal", "Forced liquidation / Liquidation borrowing", "C4-B: liquidation borrowing is liability principal inside the verified account equity scope, not a capital injection"),
            ("8", "173", "internal", "Funding rate / Funding fee expense", "Funding already reflected in equity"),
            ("8", "174", "internal", "Funding rate / Funding fee income", "Funding already reflected in equity"),
            ("9", "125", "internal", "ADL / ADL close long", "Forced trading close already reflected in equity"),
            ("9", "126", "internal", "ADL / ADL close short", "Forced trading close already reflected in equity"),
            ("9", "127", "internal", "ADL / ADL buy", "Forced trading activity already reflected in equity"),
            ("9", "128", "internal", "ADL / ADL sell", "Forced trading activity already reflected in equity"),
            ("10", "108", "internal", "Overloss recovery / Overloss recovery", "Account loss recovery already reflected in equity"),
            ("11", "118", "internal", "System crypto conversion / Transfer in", "System conversion remains inside account equity"),
            ("11", "119", "internal", "System crypto conversion / Transfer out", "System conversion remains inside account equity"),
            ("14", "204", "internal", "Block trade / Block trade buy", "Trading activity already reflected in equity"),
            ("14", "205", "internal", "Block trade / Block trade sell", "Trading activity already reflected in equity"),
            ("14", "206", "internal", "Block trade / Block trade open long", "Trading activity already reflected in equity"),
            ("14", "207", "internal", "Block trade / Block trade open short", "Trading activity already reflected in equity"),
            ("14", "208", "internal", "Block trade / Block trade close long", "Trading activity already reflected in equity"),
            ("14", "209", "internal", "Block trade / Block trade close short", "Trading activity already reflected in equity"),
            ("20", "220", "internal", "Token conversion / Buy", "Asset conversion remains inside account equity"),
            ("20", "221", "internal", "Token conversion / Sell", "Asset conversion remains inside account equity"),
            ("24", "270", "internal", " / Spread trade buy", "Trading activity already reflected in equity"),
            ("24", "271", "internal", " / Spread trade sell", "Trading activity already reflected in equity"),
            ("24", "272", "internal", " / Spread trade open long", "Trading activity already reflected in equity"),
            ("24", "273", "internal", " / Spread trade open short", "Trading activity already reflected in equity"),
            ("24", "274", "internal", " / ", "C2-A: OKX API guide explicitly defines subtype 274 as Spread trading close long; trading close activity remains inside verified account equity"),
            ("24", "275", "internal", " / ", "C2-A: OKX API guide explicitly defines subtype 275 as Spread trading close short; trading close activity remains inside verified account equity"),
            ("27", "318", "internal", "Convert / Convert in", "Asset conversion remains inside account equity"),
            ("27", "319", "internal", "Convert / Convert out", "Asset conversion remains inside account equity"),
            ("27", "379", "internal", "Convert / Auto convert in", "Asset conversion remains inside account equity"),
            ("27", "380", "internal", "Convert / Auto convert out", "Asset conversion remains inside account equity"),
            ("28", "236", "internal", "Easy convert / Easy convert in", "Asset conversion remains inside account equity"),
            ("28", "237", "internal", "Easy convert / Easy convert out", "Asset conversion remains inside account equity"),
            ("30", "320", "internal", "Simple trade / Simple buy", "Trading activity already reflected in equity"),
            ("30", "321", "internal", "Simple trade / Simple sell", "Trading activity already reflected in equity"),
            ("34", "355", "internal", "Settlement / Settlement PnL", "Realized PnL already reflected in equity"),
            ("4", "114", "internal", "Auto token conversion / Forced repayment buy", "OKX API guide lists forced repayment buy as a trade fill; forced repayment trading is already reflected in account equity"),
            ("4", "115", "internal", "Auto token conversion / Forced repayment sell", "OKX API guide lists forced repayment sell as a trade fill; forced repayment trading is already reflected in account equity"),
            ("4", "312", "internal", "Auto token conversion / Auto liability offset", "C4-B: automatic liability offset is liability settlement inside the verified account equity scope"),
            ("4", "376", "internal", "Auto token conversion / ", "C2-A/C4-B: OKX API guide defines subtype 376 as Collateralized borrowing auto conversion buy; OKX forced-repayment documentation describes account assets being converted to reduce an in-scope borrowing liability without an identified account-scope crossing"),
            ("4", "377", "internal", "Auto token conversion / ", "C2-A/C4-B: OKX API guide defines subtype 377 as Collateralized borrowing auto conversion sell; OKX forced-repayment documentation describes account assets being converted to reduce an in-scope borrowing liability without an identified account-scope crossing"),
            ("5", "16", "internal", "Forced liquidation / Forced repay", "OKX API guide lists forced repayment in the liquidation lifecycle; the account-risk event is already reflected in equity"),
            ("5", "17", "internal", "Forced liquidation / Forced borrow to repay", "OKX API guide lists forced borrowing to repay interest in the liquidation lifecycle; principal/interest effects remain in account equity"),
            ("13", "131", "internal", "DDH / DDH buy", "OKX API changelog defines DDH as Delta dynamic hedge and subtype 131 as DDH buy; trading activity is already reflected in equity"),
            ("13", "132", "internal", "DDH / DDH sell", "OKX API changelog defines DDH as Delta dynamic hedge and subtype 132 as DDH sell; trading activity is already reflected in equity"),
            ("16", "306", "internal", "Borrowing / Manual borrow", "C4-B: OKX documents borrowing as a trading-account liability under account adjusted equity; principal movement remains inside the verified account equity scope"),
            ("16", "307", "internal", "Borrowing / Auto-borrow", "C4-B: OKX documents borrowing as a trading-account liability under account adjusted equity; principal movement remains inside the verified account equity scope"),
            ("16", "308", "internal", "Borrowing / Manual repay", "C4-B: OKX documents repayment of trading-account liabilities; principal repayment remains inside the verified account equity scope"),
            ("16", "309", "internal", "Borrowing / Auto-repay", "C4-B: OKX documents repayment of trading-account liabilities; principal repayment remains inside the verified account equity scope"),
            ("29", "224", "internal", "One-click repay / One-click repay in", "C4-B: OKX documents One-click repay under the Trading account as selling account balances to repay liabilities; the liability settlement remains inside verified account equity"),
            ("29", "225", "internal", "One-click repay / One-click repay out", "C4-B: OKX documents One-click repay under the Trading account as selling account balances to repay liabilities; the liability settlement remains inside verified account equity"),
            ("6", "332", "forbidden", "Margin transfer / Margin in", "C1-B: margin-transfer activity belongs to unsupported MARGIN position/account allocation rather than the dedicated catOS USDT-M SWAP strategy"),
            ("6", "333", "forbidden", "Margin transfer / Margin out", "C1-B: margin-transfer activity belongs to unsupported MARGIN position/account allocation rather than the dedicated catOS USDT-M SWAP strategy"),
            ("6", "334", "forbidden", "Margin transfer / Margin offset", "C1-B: margin-transfer activity belongs to unsupported MARGIN position/account allocation rather than the dedicated catOS USDT-M SWAP strategy"),
            ("37", "422", "internal", "Corporate action / Corporate action: open long", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position open adjustment"),
            ("37", "423", "internal", "Corporate action / Corporate action: open short", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position open adjustment"),
            ("37", "424", "internal", "Corporate action / Corporate action: close long", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position close adjustment"),
            ("37", "425", "internal", "Corporate action / Corporate action: close short", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position close adjustment"),
            ("37", "426", "internal", "Corporate action / Corporate action: buy", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position adjustment"),
            ("37", "427", "internal", "Corporate action / Corporate action: sell", "C2-A: OKX Stock Perpetual corporate-action rebase documentation states that position/account-equity adjustments are value-neutral; this subtype is an in-account position adjustment"),
        )
    ),
    complete=False,
)


def flow_classification_id(classifications):
    return classifications.classification_id if isinstance(classifications, FlowClassification) else None


def flow_classification_complete(classifications):
    return classifications.complete if isinstance(classifications, FlowClassification) else False


def flow_classification_mapping(classifications):
    if classifications is None:
        return {}
    if isinstance(classifications, FlowClassification):
        return classifications.mapping()
    if not isinstance(classifications, Mapping):
        raise ValueError("invalid flow classifications")
    return dict(classifications)


def evidence_issues(evidence, *, account, environment, now_ms, max_age_ms, max_skew_ms):
    """Explicit test parameters only; no production freshness defaults."""
    for name, value in (("now", now_ms), ("age", max_age_ms), ("skew", max_skew_ms)):
        ipc.integer(value, name)
    issues = set()
    if not evidence:
        return frozenset({"missing_evidence"})
    for e in evidence:
        if (e.account, e.environment) != (account, environment):
            issues.add("scope_mismatch")
        if not e.complete:
            issues.add("incomplete_coverage")
        if e.source_ms > e.received_ms + max_skew_ms or e.received_ms > now_ms:
            issues.add("clock_mismatch")
        if now_ms - min(e.source_ms, e.received_ms) > max_age_ms:
            issues.add("stale")
    if max(e.source_ms for e in evidence) - min(e.source_ms for e in evidence) > max_skew_ms:
        issues.add("snapshot_skew")
    return frozenset(issues)


def usdt_equity(payload):
    """Narrow fixture profile: single USDT equity, no liabilities/other assets.

    Does not establish account eligibility or margin sufficiency. Never uses USD
    totalEq/adjEq as USDT. Unsupported balance profiles fail closed for this decoder.
    """
    data = rows(payload)
    if len(data) != 1 or not isinstance(data[0].get("details"), list):
        raise ValueError("one account balance required")
    details = data[0]["details"]
    if len(details) != 1 or details[0].get("ccy") != "USDT":
        raise ValueError("unsupported collateral profile")
    if number(details[0], "liab") != 0:
        raise ValueError("unsupported liabilities")
    verified = number(details[0], "eq")
    return verified, verified  # P3a: E_verified, E_risk; no equity buffer.


@dataclass(frozen=True)
class Order:
    symbol: str
    order_id: str
    client_id: str
    side: str
    state: str
    size: Decimal
    filled: Decimal
    updated_ms: int


def order(row):
    if row.get("instType") != "SWAP" or not text(row, "instId").endswith("-USDT-SWAP"):
        raise ValueError("unsupported instrument")
    if row.get("tdMode") != "cross" or row.get("posSide") != "net":
        raise ValueError("unsupported position mode")
    if row.get("side") not in ("buy", "sell"):
        raise ValueError("invalid side")
    if row.get("state") not in ("live", "partially_filled", "filled", "canceled", "mmp_canceled"):
        raise ValueError("unknown order state")
    size, filled = number(row, "sz"), number(row, "accFillSz")
    if not 0 <= filled <= size or size <= 0:
        raise ValueError("invalid order quantities")
    stamp = text(row, "uTime")
    if not stamp.isascii() or not stamp.isdigit():
        raise ValueError("invalid order timestamp")
    client_id = row.get("clOrdId", "")
    if not isinstance(client_id, str):
        raise ValueError("invalid client id")
    return Order(row["instId"], text(row, "ordId"), client_id, row["side"],
                 row["state"], size, filled, int(stamp))


def merge_orders(observations):
    """Dedup by exchange ID, retaining timestamp conflicts as unresolved evidence."""
    merged, issues = {}, set()
    for item in observations:
        old = merged.get(item.order_id)
        if old is not None:
            if (old.symbol, old.client_id, old.side) != (item.symbol, item.client_id, item.side):
                issues.add("order_identity_conflict")
            if old.updated_ms == item.updated_ms and old != item:
                issues.add("same_time_conflict")
            if old.updated_ms > item.updated_ms:
                issues.add("out_of_order")
                continue
            if item.filled < old.filled:
                issues.add("cumulative_regression")
        merged[item.order_id] = item
    return merged, frozenset(issues)


def fill_totals(fill_rows):
    """Quantity by order and signed fees by currency; tradeId scoped to symbol."""
    seen, quantities, fees = {}, {}, {}
    with localcontext(research._CONTEXT):
        for row in fill_rows:
            key = text(row, "instId"), text(row, "tradeId")
            value = (text(row, "ordId"), number(row, "fillSz"),
                     number(row, "fillPx"), number(row, "fee"), text(row, "feeCcy"))
            if value[1] <= 0 or value[2] <= 0:
                raise ValueError("invalid fill")
            if key in seen:
                if seen[key] != value:
                    raise ValueError("conflicting duplicate fill")
                continue
            seen[key] = value
            oid, quantity, _, fee, currency = value
            quantities[oid] = quantities.get(oid, Decimal(0)) + quantity
            fees[currency] = fees.get(currency, Decimal(0)) + fee
    return quantities, fees


def reconcile(orders, fill_rows, *, owned_order_ids, unresolved_local_ids, evidence_problems):
    """Return discrepancies only, never a trade authorization or G complete report.

    Historical fills need the matching historical order rows in this audit window.
    Ownership must come from durable local attribution, never tag/clOrdId guessing.
    """
    merged, conflicts = merge_orders(orders)
    quantities, fees = fill_totals(fill_rows)
    issues = set(evidence_problems) | set(conflicts)
    for oid, item in merged.items():
        if oid not in owned_order_ids:
            issues.add("foreign_order")
        if quantities.get(oid, Decimal(0)) != item.filled:
            issues.add("fill_gap")
        if item.state == "filled" and item.filled != item.size:
            issues.add("invalid_terminal")
    if quantities.keys() - merged.keys():
        issues.add("orphan_fill")
    if unresolved_local_ids:
        issues.add("local_unknown")  # absence from a response cannot clear UNKNOWN.
    return frozenset(issues), fees


def external_flows(bill_rows, classifications):
    """Legacy two-value consumer: forbidden bills remain blocking unresolved IDs."""
    total, unknown, forbidden = classify_bill_flows(bill_rows, classifications)
    return total, unknown | forbidden


def classify_bill_flows(bill_rows, classifications):
    """Return external total, unknown IDs and known forbidden IDs separately."""
    classifications = flow_classification_mapping(classifications)
    seen, total, unknown, forbidden = {}, Decimal(0), set(), set()
    with localcontext(research._CONTEXT):
        for row in bill_rows:
            bid = text(row, "billId")
            value = (text(row, "type"), text(row, "subType"),
                     text(row, "ccy"), number(row, "balChg"))
            if bid in seen:
                if seen[bid] != value:
                    raise ValueError("conflicting duplicate bill")
                continue
            seen[bid] = value
            category = classifications.get(value[:2])
            if category == "forbidden":
                forbidden.add(bid)
            elif category not in ("external", "internal") or value[2] != "USDT":
                unknown.add(bid)
            elif category == "external":
                total += value[3]
    return total, frozenset(unknown), frozenset(forbidden)
