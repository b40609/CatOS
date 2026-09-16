"""I-b-4 one-shot runner for the specifically authorized Demo collection.

No import-time I/O. Only main(--execute-authorized) reads the designated file and
opens the fixed Demo connection. Verification must use parse_credentials/run_once
with synthetic input and a fake Sender, never the real credential loader.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import time

from catos.account_report import build_report, decode_row
from catos.bounded_pagination import RetryPolicy
from catos.okx_collection import (
    CollectionInterrupted, CollectionPlan, ENDPOINTS, PageRequest, PageResponse, RunScope,
    collect_plan,
)
from catos.okx_http import (
    DemoReadTransport, GLOBAL_DEMO_HOST, HTTPOptions, HTTPSGetSender,
    MemoryCredentials,
)


AUTHORIZED_CREDENTIAL_FILE = Path(r"C:\Users\user\Desktop\OKX_API.txt")
MAX_CREDENTIAL_BYTES = 16384
ENDPOINT_ALIASES = (
    "account_config", "public_time", "account_instruments", "public_instruments",
    "balance", "positions", "orders_pending", "algo_pending", "mark_price",
    "orders_history", "fills", "bills", "algo_history",
)


class SetupError(ValueError):
    """Fixed public code only, never a parser exception or credential contents."""


def _profile_entries(text):
    default_profile = None
    profiles = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            matched = re.fullmatch(r"\[profiles\.([A-Za-z0-9_.-]+)\]", line)
            if matched is None or matched.group(1) in profiles:
                raise ValueError()
            current = matched.group(1)
            profiles[current] = {}
            continue
        matched = re.fullmatch(r"([^:=\uff1a]+?)\s*[:=\uff1a]\s*(.+)", line)
        if matched is None:
            raise ValueError()
        key, value = matched.groups()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError()
            value = value[1:-1]
        normalized = re.sub(r"[ _-]", "", key).lower()
        if current is None:
            if normalized != "defaultprofile" or default_profile is not None:
                raise ValueError()
            default_profile = value
        else:
            if normalized in profiles[current]:
                raise ValueError()
            profiles[current][normalized] = value
    if default_profile is None or default_profile not in profiles:
        raise ValueError()
    selected = profiles[default_profile]
    if selected.get("demo", "").lower() not in ("true", "1", "yes", "y"):
        raise ValueError()
    allowed = {"apikey", "secret", "secretkey", "apisecret", "apisecretkey",
               "okxapikey", "okxsecretkey", "okxapisecret", "passphrase",
               "apipassphrase", "okxpassphrase", "okxapipassphrase", "demo"}
    if any(key not in allowed for profile in profiles.values() for key in profile):
        raise ValueError()
    return [(key, value) for key, value in selected.items() if key != "demo"]


def parse_credentials(text):
    """Parse one explicit credential triple; no scanning or positional guessing.

    Accept flat JSON, labelled key=value/key:value lines, or an explicit
    default_profile -> [profiles.<name>] selection. Unknown/duplicate labels,
    ambiguous profile selection and missing fields fail before any connection.
    """
    try:
        if type(text) is not str or not text.strip() or len(text) > MAX_CREDENTIAL_BYTES:
            raise ValueError()
        text = text.lstrip("\ufeff").strip()
        if text.startswith("{"):
            def pairs(items):
                result = {}
                for k, v in items:
                    if k in result:
                        raise ValueError()
                    result[k] = v
                return result
            source = json.loads(text, object_pairs_hook=pairs)
            if type(source) is not dict:
                raise ValueError()
            entries = source.items()
        elif any(line.strip().startswith("[profiles.") for line in text.splitlines()):
            entries = _profile_entries(text)
        else:
            entries = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                matched = re.fullmatch(r"([^:=\uff1a]+?)\s*[:=\uff1a]\s*(.+)", line)
                if matched is None:
                    raise ValueError()
                key, value = matched.groups()
                if value.startswith(('"', "'")):
                    if len(value) < 2 or value[-1] != value[0]:
                        raise ValueError()
                    value = value[1:-1]
                entries.append((key, value))
        aliases = {
            "apikey": "api_key", "okxapikey": "api_key",
            "secret": "secret", "secretkey": "secret", "apisecret": "secret",
            "apisecretkey": "secret", "okxsecretkey": "secret", "okxapisecret": "secret",
            "passphrase": "passphrase", "apipassphrase": "passphrase",
            "okxpassphrase": "passphrase", "okxapipassphrase": "passphrase",
        }
        values = {}
        for key, value in entries:
            if type(key) is not str or type(value) is not str:
                raise ValueError()
            canonical = aliases.get(re.sub(r"[ _-]", "", key).lower())
            if canonical is None or canonical in values:
                raise ValueError()
            values[canonical] = value
        if set(values) != {"api_key", "secret", "passphrase"}:
            raise ValueError()
        return MemoryCredentials(**values)
    except Exception:
        raise SetupError("credential_format_unsupported") from None


def load_authorized_credentials():
    """Read only the user-designated file, with a size bound and no redirection.

    This is the sole real credential access path authorized for I-b-4. It is not
    an environment loader or permission for any other credential discovery.
    """
    try:
        path = AUTHORIZED_CREDENTIAL_FILE
        # Reject a symlink/junction that would resolve to another credential file.
        if path.resolve(strict=True) != path.absolute():
            raise SetupError("credential_path_redirected")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CREDENTIAL_BYTES + 1)
        if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
            raise SetupError("credential_file_size_invalid")
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        return parse_credentials(raw.decode(encoding))
    except SetupError:
        raise
    except UnicodeError:
        raise SetupError("credential_encoding_unsupported") from None
    except Exception:
        raise SetupError("credential_file_unavailable") from None


class _Clock:
    @staticmethod
    def wall_ms():
        return time.time_ns() // 1_000_000

    @staticmethod
    def monotonic_ms():
        return time.monotonic_ns() // 1_000_000


def authorized_scope(end_ms):
    """Freeze the approved trailing 24h window once, before the first request."""
    return RunScope("okx-demo", "demo", "BTC-USDT-SWAP", end_ms - 86400000,
                    end_ms, 120, 40, 10000, 180000)


def read_config_mode_once(credentials, *, sender, clock=None, sleep_ms=None):
    """Perform exactly one authorized Demo account-config GET and expose mode only."""
    active_clock = clock or _Clock()
    scope = authorized_scope(active_clock.wall_ms())
    pause = sleep_ms or (lambda ms: time.sleep(ms / 1000))
    transport = DemoReadTransport(scope, HTTPOptions(host=GLOBAL_DEMO_HOST), credentials,
        sender=sender, wall_ms=active_clock.wall_ms, monotonic_ms=active_clock.monotonic_ms,
        sleep_ms=pause)
    request = PageRequest(ENDPOINTS["account_config"], scope, 1, None, scope.request_timeout_ms)
    try:
        response = transport.fetch(request)
        if (not isinstance(response, PageResponse) or response.payload.get("code") != "0"
                or response.next_cursor is not None
                or (response.account_alias, response.environment) !=
                   (scope.account_alias, scope.environment)):
            raise ValueError()
        data = response.payload.get("data")
        if type(data) is not list or len(data) != 1:
            raise ValueError()
        fact = decode_row("account_config", data[0])
        if fact["is_subaccount"]:
            raise SetupError("config_not_main_account")
        return {"acctLv": fact["acctLv"], "posMode": fact["posMode"]}
    except SetupError:
        raise
    except Exception:
        raise SetupError("config_mode_read_failed") from None


class _ConfigGate:
    """Block later HTTP calls unless the first config passes the declared checks.

    Preserve the config page for the decoder even if its contents fail the gate.
    The next driver attempt interrupts locally; no separate run resets budgets.
    """

    def __init__(self, transport):
        self.transport = transport
        self.passed = False
        self.issues = {"config_not_verified"}

    def fetch(self, request):
        if request.endpoint.alias != "account_config" and not self.passed:
            raise CollectionInterrupted()
        response = self.transport.fetch(request)
        if request.endpoint.alias != "account_config":
            return response
        problems = set()
        try:
            if (not isinstance(response, PageResponse) or response.payload.get("code") != "0"
                    or response.next_cursor is not None
                    or (response.account_alias, response.environment) !=
                       (request.scope.account_alias, request.scope.environment)):
                raise ValueError()
            data = response.payload.get("data")
            if type(data) is not list or len(data) != 1:
                raise ValueError()
            fact = decode_row("account_config", data[0])
            if fact["is_subaccount"]:
                problems.add("config_not_main_account")
            if fact["posMode"] != "net_mode" or fact["acctLv"] not in ("2", "3"):
                problems.add("config_mode_mismatch")
            permissions = fact["perm"].split(",")
            if (len(set(permissions)) != len(permissions)
                    or "read_only" not in permissions
                    or any(p not in ("read_only", "trade") for p in permissions)):
                problems.add("config_permission_mismatch")
            if fact["roleType"] not in ("0", "1", "2"):
                problems.add("config_role_unknown")
        except (ValueError, TypeError, AttributeError):
            problems.add("config_invalid")
        self.issues = problems
        self.passed = not problems
        return response


@dataclass(frozen=True, repr=False)
class CollectionOutcome:
    report: dict = field(repr=False)
    audit: dict = field(repr=False)
    summary: dict = field(repr=False)

    def __repr__(self):
        return "CollectionOutcome(<private; use summary>)"


def run_once(credentials, *, sender, clock=None, sleep_ms=None):
    """One approved scope, injected sender required, no output/files/DB access.

    Caller must inject synthetic credentials and fake sender for unit tests.
    The real CLI supplies HTTPSGetSender only after its explicit execution flag.
    """
    active_clock = clock or _Clock()
    scope = authorized_scope(active_clock.wall_ms())
    pause = sleep_ms or (lambda ms: time.sleep(ms / 1000))
    transport = DemoReadTransport(scope, HTTPOptions(host=GLOBAL_DEMO_HOST), credentials,
        sender=sender, wall_ms=active_clock.wall_ms, monotonic_ms=active_clock.monotonic_ms,
        sleep_ms=pause)
    gate = _ConfigGate(transport)
    result = collect_plan(CollectionPlan(scope, ENDPOINT_ALIASES), gate,
        clock=active_clock, retry_policy=RetryPolicy(max_retries_per_page=2), sleep_ms=pause,
        stop_on_incomplete=("account_config",))
    if not result.manifest.endpoint_manifests[0].complete:
        gate.passed = False
        gate.issues.add("config_not_verified")
    report = build_report(result, scope=scope)
    # No local trading DB was loaded. Never manufacture ownership or flow classes.
    # Keep this outside the report so the decoder's content_digest stays valid.
    # I-b-4 is explicitly authorized to use the designated Demo main account.
    # account_report keeps the project's broader subaccount policy signal, so
    # suppress only that policy discrepancy in this one-shot runner.
    report_notes = set(report["discrepancies"]) - {"not_subaccount"}
    notes = sorted(report_notes | gate.issues | {"local_attribution_not_loaded"})
    complete = report["collection_complete"] and gate.passed
    sources = []
    for manifest in result.manifest.endpoint_manifests:
        sources.append({"alias": manifest.alias, "complete": manifest.complete,
                        "started": manifest.started_ms is not None,
                        "attempts": manifest.requests, "pages": len(manifest.pages)})
    summary = {
        "version": "i-b-4.v1", "status": "collected" if complete else "incomplete",
        "account_alias": scope.account_alias, "environment": scope.environment,
        "host": GLOBAL_DEMO_HOST, "instrument": scope.instrument,
        "window_start_ms": scope.window_start_ms, "window_end_ms": scope.window_end_ms,
        "started_ms": result.manifest.started_ms, "completed_ms": result.manifest.completed_ms,
        "config_gate_passed": gate.passed,
        "identity_basis": "user_designated_credential_file_and_main_account_relation",
        "expected_uid_independently_matched": False,
        "collection_complete": bool(complete), "reconciled": False, "trade_authorized": False,
        "attempts": result.manifest.requests, "wire_attempts": transport.audit()["wire_attempts"],
        "fact_counts": dict(sorted(Counter(f["kind"] for f in report["facts"]).items())),
        "sources": sources, "discrepancies": notes,
        # Fixed decoder field/reason enums only; omit row values and identifiers.
        "record_diagnostics": [
            {"alias": alias, "field": field, "reason": reason, "count": count}
            for (alias, field, reason), count in sorted(Counter(
                (item["alias"], item["field"], item["reason"])
                for item in report["record_diagnostics"]
            ).items())
        ],
        "report_content_digest": report["content_digest"],
    }
    return CollectionOutcome(report, transport.audit(), summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Authorized I-b-4 single Demo read-only collection")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--execute-authorized", action="store_true",
                         help="read the specifically authorized credential file and run once")
    actions.add_argument("--read-config-mode-authorized", action="store_true",
                         help="perform one authorized Demo account-config GET and print mode only")
    args = parser.parse_args(argv)
    if not args.execute_authorized and not args.read_config_mode_authorized:
        parser.print_help()
        return 0
    try:
        credentials = load_authorized_credentials()
        if args.read_config_mode_authorized:
            config_mode = read_config_mode_once(credentials, sender=HTTPSGetSender())
            print(json.dumps(config_mode, ensure_ascii=True, sort_keys=True))
            return 0
        outcome = run_once(credentials, sender=HTTPSGetSender())
        # No facts, monetary amounts, IDs, headers, raw data or credentials printed.
        print(json.dumps(outcome.summary, ensure_ascii=True, sort_keys=True))
        return 0 if outcome.summary["collection_complete"] else 2
    except SetupError as exc:
        print(json.dumps({"status": "not_started", "issue": str(exc)}))
        return 2
    except KeyboardInterrupt:
        print('{"status":"interrupted","issue":"manual_interruption"}')
        return 2
    except Exception:
        # Never emit a traceback, exception message or locals containing secrets.
        print('{"status":"failed","issue":"collection_execution_failed"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
