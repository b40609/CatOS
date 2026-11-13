"""Local, append-only approvals that let one research strategy run on a local-sim Bot.

2026-11-12 (docs/step2-research-to-bot-proposal.md, approved as "完全同意建議"):
the unit of approval is a deployment profile (strategy, version, source sha256,
manifest sha256, parameters, contracts, instrument, timeframe, warm-up, plus the
replay's capital and cost parameters). Records live in a git-ignored JSON Lines
file; every line stores the sha256 of the previous line, so an edited, removed
or reordered line breaks the chain and every read fails closed.

Only the user approves or revokes, from an interactive terminal, by typing the
full 64-character source sha256 and then ``approve``/``revoke``. Agents must not
run those commands or edit the file (AGENTS.md 紅線). This is a procedural guard
against wiring a research strategy into a Bot by accident, not a security
boundary: a deliberate local program can still write the file.

``CATOS_STRATEGY_APPROVALS`` overrides the file path. It exists for isolated
tests and self-tests with test records; every replay records the path it used.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from catos import research_catalog

ENV_PATH = "CATOS_STRATEGY_APPROVALS"
DEFAULT_PATH = research_catalog.ROOT / "outputs" / "strategy-approvals" / "approvals.jsonl"
SCHEMA = "catos.strategy-approval"
SCHEMA_VERSION = 1
PROFILE_SCHEMA = "catos.strategy-deployment"
GENESIS = "0" * 64
MAX_FILE_BYTES = 4_000_000
MAX_RECORDS = 10_000
# IPC frames carry the restart history (ipc.MAX_BOT_LOOKBACK bars); keep both equal.
MAX_BOT_LOOKBACK = 512
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_ID = re.compile(r"[0-9a-f]{32}\Z")
_INST_ID = re.compile(r"[A-Z0-9]+-USDT-SWAP\Z")
_BASIS = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z")
PROFILE_FIELDS = frozenset({
    "schema", "schema_version", "strategy_id", "version", "parameters", "quantity", "inst_id",
    "timeframe_ms", "warmup_bars", "initial_balance", "fee_rate", "slippage_bps",
})
APPROVE_FIELDS = frozenset({
    "schema", "schema_version", "record_id", "prev_sha256", "action", "created_at",
    "strategy_id", "version", "entry", "source_sha256", "manifest_sha256", "profile", "research_basis",
})
REVOKE_FIELDS = frozenset({
    "schema", "schema_version", "record_id", "prev_sha256", "action", "created_at", "approval_id",
})
TIMEFRAMES_MS = frozenset({300_000, 900_000, 3_600_000, 14_400_000})


class ApprovalError(ValueError):
    pass


@dataclass(frozen=True)
class BotStrategy:
    """A research strategy whose whole state is the last ``lookback`` closed bars.

    Only these can go on a Bot: a restarted Worker is restored by re-feeding the
    ledger's committed bars as warm-up, never from serialized strategy state.
    """
    strategy_id: str
    version: str
    lookback_parameter: str

    @property
    def research(self):
        return research_catalog.strategy_spec(self.strategy_id)

    def lookback(self, parameters):
        return parameters[self.lookback_parameter]


# Package E/F strategies keep state over their whole history (trailing stops,
# exponentially weighted variance), so they are not eligible.
BOT_STRATEGIES = {
    (research_catalog.DONCHIAN_ID, research_catalog.DONCHIAN_VERSION):
        BotStrategy(research_catalog.DONCHIAN_ID, research_catalog.DONCHIAN_VERSION, "entry_bars"),
}


def bot_strategy(strategy_id, version):
    entry = BOT_STRATEGIES.get((strategy_id, version)) if type(strategy_id) is str and type(version) is str else None
    if entry is None:
        raise ApprovalError("strategy_not_bot_eligible")
    return entry


def approvals_path():
    override = os.environ.get(ENV_PATH)
    return Path(override) if override else DEFAULT_PATH


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ApprovalError("approval_duplicate_field")
            result[key] = value
        return result

    def reject(_value):
        raise ApprovalError("approval_invalid_json_constant")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject, parse_float=reject)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApprovalError("approval_invalid_json") from None


def _decimal(value, name, low, high, *, whole=False):
    if type(value) is not str or not 1 <= len(value) <= 64 or value.strip() != value:
        raise ApprovalError(f"profile_{name}_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ApprovalError(f"profile_{name}_invalid") from None
    if not number.is_finite() or not low <= number <= high or (whole and number % 1):
        raise ApprovalError(f"profile_{name}_out_of_range")
    if str(number) != value:
        raise ApprovalError(f"profile_{name}_not_canonical")
    return number


def validate_profile(value):
    """The approval unit; every field must be present and canonical (fail closed)."""
    if type(value) is not dict or set(value) != PROFILE_FIELDS:
        raise ApprovalError("profile_exact_fields_required")
    if value["schema"] != PROFILE_SCHEMA or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ApprovalError("profile_schema_mismatch")
    bot = bot_strategy(value["strategy_id"], value["version"])
    spec = bot.research
    parameters = value["parameters"]
    names = [name for name, _, _ in spec.parameters]
    if type(parameters) is not dict or set(parameters) != set(names):
        raise ApprovalError("profile_parameters_exact_fields_required")
    for name, low, high in spec.parameters:
        if type(parameters[name]) is not int or not low <= parameters[name] <= high:
            raise ApprovalError(f"profile_{name}_out_of_range")
    if spec.strategy_id == research_catalog.DONCHIAN_ID and parameters["exit_bars"] >= parameters["entry_bars"]:
        raise ApprovalError("profile_exit_bars_must_be_below_entry_bars")
    lookback = bot.lookback(parameters)
    if lookback > MAX_BOT_LOOKBACK:
        raise ApprovalError("profile_lookback_above_bot_limit")
    _decimal(value["quantity"], "quantity", Decimal("1"), Decimal("1000"), whole=True)
    if type(value["inst_id"]) is not str or _INST_ID.fullmatch(value["inst_id"]) is None:
        raise ApprovalError("profile_inst_id_invalid")
    if type(value["timeframe_ms"]) is not int or value["timeframe_ms"] not in TIMEFRAMES_MS:
        raise ApprovalError("profile_timeframe_invalid")
    warmup = value["warmup_bars"]
    if type(warmup) is not int or not lookback <= warmup < spec.warmup_limit:
        raise ApprovalError("profile_warmup_bars_invalid")
    _decimal(value["initial_balance"], "initial_balance", Decimal("1"), Decimal("1000000000"))
    _decimal(value["fee_rate"], "fee_rate", Decimal("0"), Decimal("0.01"))
    _decimal(value["slippage_bps"], "slippage_bps", Decimal("0"), Decimal("100"))
    return json.loads(canonical(value))


def load_profile(path):
    raw = Path(path).read_bytes()
    if len(raw) > 8192:
        raise ApprovalError("profile_too_large")
    return validate_profile(_strict_json(raw.decode("utf-8")))


def _record_id(body):
    return _sha256(canonical({k: v for k, v in body.items() if k != "record_id"}).encode("utf-8"))[:32]


def _check_record(record, prev):
    if type(record) is not dict or record.get("schema") != SCHEMA or record.get("schema_version") != SCHEMA_VERSION:
        raise ApprovalError("approval_schema_mismatch")
    action = record.get("action")
    if action == "approve":
        fields = APPROVE_FIELDS
    elif action == "revoke":
        fields = REVOKE_FIELDS
    else:
        raise ApprovalError("approval_action_invalid")
    if set(record) != fields:
        raise ApprovalError("approval_exact_fields_required")
    if record["prev_sha256"] != prev:
        raise ApprovalError("approval_chain_broken")
    if type(record["record_id"]) is not str or record["record_id"] != _record_id(record):
        raise ApprovalError("approval_record_id_mismatch")
    try:
        stamp = datetime.fromisoformat(record["created_at"])
    except (TypeError, ValueError):
        raise ApprovalError("approval_created_at_invalid") from None
    if stamp.utcoffset() is None:
        raise ApprovalError("approval_created_at_invalid")
    if action == "revoke":
        if type(record["approval_id"]) is not str or _RECORD_ID.fullmatch(record["approval_id"]) is None:
            raise ApprovalError("approval_revoke_target_invalid")
        return
    for name in ("source_sha256", "manifest_sha256"):
        if type(record[name]) is not str or _SHA256.fullmatch(record[name]) is None:
            raise ApprovalError(f"approval_{name}_invalid")
    if type(record["entry"]) is not str or not record["entry"]:
        raise ApprovalError("approval_entry_invalid")
    basis = record["research_basis"]
    if basis is not None and (type(basis) is not str or _BASIS.fullmatch(basis) is None):
        raise ApprovalError("approval_research_basis_invalid")
    profile = validate_profile(record["profile"])
    if (profile["strategy_id"], profile["version"]) != (record["strategy_id"], record["version"]):
        raise ApprovalError("approval_profile_identity_mismatch")


def read_records(path=None):
    """Every record in order; any doubt about the file raises (fail closed)."""
    path = approvals_path() if path is None else Path(path)
    if path.is_symlink():
        raise ApprovalError("approval_file_symlink_rejected")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        return []
    except OSError:
        raise ApprovalError("approval_file_unavailable") from None
    if len(raw) > MAX_FILE_BYTES:
        raise ApprovalError("approval_file_too_large")
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise ApprovalError("approval_file_truncated")
    records = []
    prev = GENESIS
    approved = set()
    revoked = set()
    for line in raw.split(b"\n")[:-1]:
        record = _strict_json(line.decode("utf-8"))
        _check_record(record, prev)
        if canonical(record).encode("utf-8") != line:
            raise ApprovalError("approval_line_not_canonical")
        if record["action"] == "approve":
            approved.add(record["record_id"])
        else:
            target = record["approval_id"]
            if target not in approved or target in revoked:
                raise ApprovalError("approval_revoke_without_active_approval")
            revoked.add(target)
        records.append(record)
        if len(records) > MAX_RECORDS:
            raise ApprovalError("approval_record_limit")
        prev = _sha256(line + b"\n")
    return records


def active_approval(approval_id, path=None):
    """The approve record with this id, unless it was revoked; else ApprovalError."""
    if type(approval_id) is not str or _RECORD_ID.fullmatch(approval_id) is None:
        raise ApprovalError("approval_id_invalid")
    found = None
    for record in read_records(path):
        if record["action"] == "approve" and record["record_id"] == approval_id:
            found = record
        elif record["action"] == "revoke" and record["approval_id"] == approval_id:
            raise ApprovalError("approval_revoked")
    if found is None:
        raise ApprovalError("approval_not_found")
    return found


def active_approvals(path=None):
    records = read_records(path)
    revoked = {record["approval_id"] for record in records if record["action"] == "revoke"}
    return [record for record in records if record["action"] == "approve" and record["record_id"] not in revoked]


def find_active(profile, path=None):
    """Latest active approval whose profile equals ``profile`` exactly; else ApprovalError."""
    profile = validate_profile(profile)
    matches = [record for record in active_approvals(path) if record["profile"] == profile]
    if not matches:
        raise ApprovalError("no_active_approval_for_profile")
    return matches[-1]


def _append(body, path):
    path = Path(path)
    records = read_records(path)  # verifies the chain before extending it
    prev = GENESIS
    if records:
        prev = _sha256(path.read_bytes().split(b"\n")[-2] + b"\n")
    record = {**body, "schema": SCHEMA, "schema_version": SCHEMA_VERSION, "prev_sha256": prev}
    record["record_id"] = _record_id(record)
    _check_record(record, prev)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical(record).encode("utf-8") + b"\n"
    with path.open("ab") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    if read_records(path)[-1] != record:
        raise ApprovalError("approval_append_unverified")
    return record


def _now():
    return datetime.now(timezone.utc).isoformat()


def deployment_identity(profile):
    """Manifest and verified source hash of the profile's strategy (research white list included)."""
    spec = bot_strategy(profile["strategy_id"], profile["version"]).research
    artifact = research_catalog.load_strategy_manifest(spec)  # whitelist + current source hash
    return artifact, research_catalog.file_hash(spec.manifest)


def summary_text(profile, artifact, manifest_sha256):
    lines = [
        "策略核准（local-sim Bot 歷史重播；不涵蓋 Demo／Live）",
        f"  策略：{profile['strategy_id']} / {profile['version']}",
        f"  entry：{artifact['entry']}",
        f"  來源檔案：{', '.join(artifact['source_files'])}",
        f"  來源 sha256：{artifact['sha256']}",
        f"  manifest sha256：{manifest_sha256}",
        f"  參數：{json.dumps(profile['parameters'], ensure_ascii=False)}；張數 {profile['quantity']}",
        f"  合約／週期：{profile['inst_id']} / {profile['timeframe_ms']} ms；預熱 {profile['warmup_bars']} 根",
        f"  本金 {profile['initial_balance']}；手續費率 {profile['fee_rate']}；滑價 {profile['slippage_bps']} bps",
    ]
    return "\n".join(lines)


def approve(*, strategy_id, version, sha256, profile, confirm, research_basis=None, path=None):
    """Append an approve record after the caller's confirmation; returns the record."""
    profile = validate_profile(profile)
    if (profile["strategy_id"], profile["version"]) != (strategy_id, version):
        raise ApprovalError("profile_identity_mismatch")
    if type(sha256) is not str or _SHA256.fullmatch(sha256) is None:
        raise ApprovalError("full_sha256_required")
    artifact, manifest_sha256 = deployment_identity(profile)
    if sha256 != artifact["sha256"]:
        raise ApprovalError("sha256_does_not_match_current_source")
    if research_basis is not None and (type(research_basis) is not str or _BASIS.fullmatch(research_basis) is None):
        raise ApprovalError("approval_research_basis_invalid")
    if confirm(summary_text(profile, artifact, manifest_sha256), "approve") is not True:
        raise ApprovalError("approval_not_confirmed")
    target = approvals_path() if path is None else Path(path)
    return _append({"action": "approve", "created_at": _now(), "strategy_id": strategy_id,
                    "version": version, "entry": artifact["entry"], "source_sha256": artifact["sha256"],
                    "manifest_sha256": manifest_sha256, "profile": profile,
                    "research_basis": research_basis}, target)


def revoke(*, approval_id, confirm, path=None):
    target = approvals_path() if path is None else Path(path)
    record = active_approval(approval_id, target)
    text = (f"撤銷核准 {approval_id}：{record['strategy_id']} / {record['version']} "
            f"{json.dumps(record['profile']['parameters'], ensure_ascii=False)}；"
            "執行中的重播在下一根 K 線前停止，不平倉、不釋放合約。")
    if confirm(text, "revoke") is not True:
        raise ApprovalError("revoke_not_confirmed")
    return _append({"action": "revoke", "created_at": _now(), "approval_id": approval_id}, target)


def terminal_confirm(text, word):
    """Interactive confirmation only: a script or agent pipe cannot answer it."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ApprovalError("interactive_terminal_required")
    print(text, flush=True)
    answer = input(f"確認請輸入 {word}：")
    return answer.strip() == word


def cli_main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m catos.cli strategy",
                                     description="研究策略上 local-sim Bot 的本機核准（只限使用者在終端機執行）")
    commands = parser.add_subparsers(dest="command", required=True)
    approve_cmd = commands.add_parser("approve", help="核准一份部署設定")
    approve_cmd.add_argument("--strategy", required=True)
    approve_cmd.add_argument("--version", required=True)
    approve_cmd.add_argument("--sha256", required=True, help="完整 64 碼來源 sha256")
    approve_cmd.add_argument("--profile", required=True, help="部署設定 JSON 檔")
    approve_cmd.add_argument("--research-basis", default=None, help="研究依據（選填，例如研究任務 id）")
    revoke_cmd = commands.add_parser("revoke", help="撤銷一筆核准")
    revoke_cmd.add_argument("--approval-id", required=True)
    commands.add_parser("list", help="列出核准紀錄（唯讀）")
    commands.add_parser("identity", help="列出可上 Bot 的研究策略與目前來源 sha256（唯讀）")
    args = parser.parse_args(argv)
    try:
        if args.command == "approve":
            record = approve(strategy_id=args.strategy, version=args.version, sha256=args.sha256,
                             profile=load_profile(args.profile), confirm=terminal_confirm,
                             research_basis=args.research_basis)
            print(f"已核准：approval_id={record['record_id']}（{approvals_path()}）")
        elif args.command == "revoke":
            record = revoke(approval_id=args.approval_id, confirm=terminal_confirm)
            print(f"已撤銷：{args.approval_id}（紀錄 {record['record_id']}）")
        elif args.command == "list":
            records = read_records()
            revoked = {r["approval_id"] for r in records if r["action"] == "revoke"}
            print(f"核准紀錄：{approvals_path()}（{len(records)} 筆，雜湊鏈完整）")
            for record in records:
                if record["action"] == "approve":
                    state = "已撤銷" if record["record_id"] in revoked else "有效"
                    print(f"  {record['record_id']}  {state}  {record['strategy_id']}/{record['version']}  "
                          f"{json.dumps(record['profile']['parameters'], ensure_ascii=False)}  "
                          f"{record['profile']['inst_id']} {record['profile']['timeframe_ms']}ms  {record['created_at']}")
                else:
                    print(f"  {record['record_id']}  撤銷 {record['approval_id']}  {record['created_at']}")
        else:
            for (strategy_id, version) in BOT_STRATEGIES:
                spec = research_catalog.strategy_spec(strategy_id)
                artifact = research_catalog.load_strategy_manifest(spec)
                print(f"{strategy_id} {version} sha256={artifact['sha256']} "
                      f"manifest_sha256={research_catalog.file_hash(spec.manifest)}")
        return 0
    except (ApprovalError, ValueError, OSError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1
