"""Windows single-user account lock, independent of the selected SQLite path."""

import hashlib
import os
from pathlib import Path
import sys

from catos import ipc
from catos.ipc import token

LOCK_DIRECTORY = None  # Resolved lazily; tests replace only this internal constant.
ENVIRONMENT = "local-sim"


class AccountBusy(RuntimeError):
    pass


class AccountBindingError(RuntimeError):
    pass


class AccountLock:
    def __init__(self, account_id, environment=ENVIRONMENT):
        self.account_id = token(account_id, "simulation account_id")
        if environment != ENVIRONMENT:
            raise ValueError("only local-sim is supported")
        digest = hashlib.sha256(f"{environment}:{account_id}".encode("ascii")).hexdigest()
        directory = LOCK_DIRECTORY if LOCK_DIRECTORY is not None else Path.home() / ".catos" / "local-simulation-locks"
        self.path = directory / f"{digest}.lock"
        self._file = None

    def acquire(self):
        if sys.platform != "win32":
            raise RuntimeError("Slice E account locking is currently Windows-only")
        if self._file is not None:
            raise AccountBusy("lock already held by this instance")
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise AccountBusy("another Supervisor holds this local-sim account") from exc
        self._file = handle

    def check_database(self, database):
        if self._file is None:
            raise AccountBindingError("account lock is not held")
        self._file.seek(1)
        content = self._file.read(ipc.MAX_FRAME + 1)
        if not content:
            return False
        try:
            binding = ipc.decode_payload(content)
            ipc.exact(binding, ("database",))
            if type(binding["database"]) is not str:
                raise ValueError("invalid database path")
            bound = Path(binding["database"]).resolve()
            if os.path.normcase(str(bound)) != os.path.normcase(str(Path(database).resolve())):
                raise AccountBindingError("account is bound to a different database; no implicit reset/migration")
            if not bound.is_file():
                raise AccountBindingError("bound database missing; do not rebuild account state")
        except (ValueError, OSError) as exc:
            raise AccountBindingError("invalid account database binding; manual inspection required") from exc
        return True

    def bind_database(self, database):
        if self.check_database(database):
            return
        path = Path(database).resolve()
        if not path.is_file():
            raise AccountBindingError("initialize SQLite before binding the account")
        content = ipc.encode_frame({"database": str(path)})[4:]
        if self._file.write(content) != len(content):
            raise AccountBindingError("incomplete database binding write")
        self._file.flush()
        os.fsync(self._file.fileno())
        # A torn first write fails closed next time; never silently replaces a binding.

    def close(self):
        if self._file is not None:
            # Closing the handle also releases the OS lock after a crash.
            self._file.close()
            self._file = None
        # Never unlink: deleting a lock path can split ownership across files.
