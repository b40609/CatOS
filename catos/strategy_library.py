"""Supervisor-owned JSON metadata, using no new SQLite schema."""

from copy import deepcopy
from datetime import datetime
import os

from catos.python_strategy import artifact, binding, canonical, digest, TOKEN
from catos.local_sim_control import ControlError, strict_json, valid_id, now


class StrategyLibrary:
    def __init__(self, control):
        self.control = control
        self.value = {"contract": "catos.strategy-library.v1", "versions": {}, "bots": {}, "commands": {}}

    def open(self):
        path = self.control.root / "strategy-library.json"
        if (self.control.root / "strategy-library.pending").exists():
            raise ValueError("strategy_library_uncertain")
        if not path.exists():
            return
        with path.open("rb") as stream:
            raw = stream.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("strategy_library_limit")
        value = strict_json(raw)
        if type(value) is not dict or set(value) != set(self.value) or value["contract"] != self.value["contract"]:
            raise ValueError("strategy_library_contract")
        for field, limit in (("versions", 100), ("bots", 100), ("commands", 500)):
            if type(value[field]) is not dict or len(value[field]) > limit:
                raise ValueError("strategy_library_limit")
        identities = set()
        for key, entry in value["versions"].items():
            if type(entry) is not dict or set(entry) != {"artifact", "artifact_hash", "allowed_modes", "created_at"}:
                raise ValueError("strategy_version_contract")
            manifest = artifact(entry["artifact"])
            identity = (manifest["strategy_id"], manifest["version"])
            if identity in identities:
                raise ValueError("duplicate_strategy_identity")
            identities.add(identity)
            self.timestamp(entry["created_at"])
            if key != digest(manifest) or entry["artifact_hash"] != key or entry["allowed_modes"] != ["local"]:
                raise ValueError("strategy_library_binding")
        for bot_id, bot in value["bots"].items():
            self.validate_bot(bot)
            if bot_id != bot["bot_id"] or bot["binding"]["artifact_hash"] not in value["versions"]:
                raise ValueError("strategy_library_bot")
        for request_id, command in value["commands"].items():
            if not valid_id(request_id) or type(command) is not dict or set(command) != {"operation", "input", "result"}:
                raise ValueError("strategy_library_command")
            if command["operation"] == "create_version":
                manifest = artifact(command["input"])
                if command["result"] != value["versions"].get(digest(manifest)):
                    raise ValueError("strategy_command_binding")
            elif command["operation"] == "allocate_bot":
                self.validate_bot(command["result"])
                bot = command["result"]
                expected = {key: bot[key] for key in ("bot_id", "trusted", "mode")}
                expected.update(artifact_hash=bot["binding"]["artifact_hash"], parameters=bot["binding"]["parameters"])
                if command["input"] != expected or value["bots"].get(bot["bot_id"]) != bot:
                    raise ValueError("bot_command_binding")
            else:
                raise ValueError("strategy_command_operation")
        self.value = value

    @staticmethod
    def timestamp(value):
        if type(value) is not str or datetime.fromisoformat(value).utcoffset() is None:
            raise ValueError("strategy_timestamp")

    @staticmethod
    def validate_bot(bot):
        if (type(bot) is not dict or set(bot) != {"bot_id", "mode", "binding", "trusted", "created_at"}
                or type(bot["bot_id"]) is not str or not TOKEN.fullmatch(bot["bot_id"])
                or bot["mode"] != "local" or bot["trusted"] is not True):
            raise ValueError("bot_contract")
        binding(bot["binding"])
        StrategyLibrary.timestamp(bot["created_at"])

    def _save(self, value):
        encoded = canonical(value)
        if len(encoded.encode("utf-8")) > 4_000_000:
            raise ControlError("strategy_library_limit", 409)
        try:
            path = self.control.root / "strategy-library.pending"
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            path.replace(self.control.root / "strategy-library.json")
            self.value = deepcopy(value)
        except OSError:
            self.control.unavailable = "strategy_library_write_uncertain"
            if self.control.stop_event is not None:
                self.control.stop_event.set()
            raise ControlError(self.control.unavailable) from None

    def _command(self, request_id, operation, payload, create):
        self.control._ready()
        if not valid_id(request_id):
            raise ControlError("invalid_command_contract", 422)
        prior = self.value["commands"].get(request_id)
        if prior:
            if prior["operation"] != operation or prior["input"] != payload:
                raise ControlError("request_id_conflict", 409)
            return deepcopy(prior["result"])
        if self.control._binding(request_id):
            raise ControlError("request_id_conflict", 409)
        if self.control.current_build() != self.control.loaded_build:
            raise ControlError("source_changed_restart_required", 409)
        if len(self.value["commands"]) >= 500:
            raise ControlError("strategy_command_limit", 409)
        value = deepcopy(self.value)
        try:
            result = create(value)
        except (ValueError, SyntaxError, TypeError, KeyError) as exc:
            raise ControlError(str(exc)[:120], 422) from None
        value["commands"][request_id] = {"operation": operation, "input": payload, "result": result}
        self._save(value)
        return deepcopy(result)

    def create(self, request_id, manifest):
        def make(value):
            checked = artifact(manifest)
            artifact_hash = digest(checked)
            for entry in value["versions"].values():
                if (entry["artifact"]["strategy_id"], entry["artifact"]["version"]) == (checked["strategy_id"], checked["version"]) and entry["artifact_hash"] != artifact_hash:
                    raise ControlError("immutable_version_conflict", 409)
            entry = value["versions"].get(artifact_hash)
            if entry is None:
                if len(value["versions"]) >= 100:
                    raise ControlError("strategy_version_limit", 409)
                entry = {"artifact": checked, "artifact_hash": artifact_hash, "allowed_modes": ["local"], "created_at": now()}
                value["versions"][artifact_hash] = entry
            return entry
        return self._command(request_id, "create_version", manifest, make)

    def allocate(self, request_id, bot_id, artifact_hash, parameters, trusted, mode):
        payload = dict(bot_id=bot_id, artifact_hash=artifact_hash, parameters=parameters, trusted=trusted, mode=mode)
        def make(value):
            if type(artifact_hash) is not str or artifact_hash not in value["versions"]:
                raise ValueError("strategy_version_not_found")
            if bot_id in value["bots"]:
                raise ControlError("immutable_bot_conflict", 409)
            if len(value["bots"]) >= 100:
                raise ControlError("bot_limit", 409)
            bot = {"bot_id": bot_id, "mode": mode, "trusted": trusted, "created_at": now(),
                   "binding": {"artifact": value["versions"][artifact_hash]["artifact"], "artifact_hash": artifact_hash, "parameters": parameters}}
            self.validate_bot(bot)
            value["bots"][bot_id] = bot
            return bot
        return self._command(request_id, "allocate_bot", payload, make)

    def bot(self, bot_id):
        if type(bot_id) is not str or bot_id not in self.value["bots"]:
            raise ControlError("bot_not_found", 404)
        return deepcopy(self.value["bots"][bot_id])

    def versions(self):
        return {"items": deepcopy(list(self.value["versions"].values()))}

    def bots(self):
        return {"items": deepcopy(list(self.value["bots"].values()))}
