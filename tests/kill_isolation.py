"""Module-level isolation of the Kill-Switch record file (work package B).

Test modules that start local-sim runs, replays or R4 cases import
``setUpModule``/``tearDownModule`` from here, so they never read the
workspace's real ``outputs/controls/kill-switch.jsonl``: a switch the user
engaged must not make the suite fail (and tempt anyone to clear it).
"""
import os
import tempfile
from pathlib import Path

from catos import kill_switch

_saved = {}


def setUpModule():
    directory = tempfile.TemporaryDirectory()
    _saved["directory"] = directory
    _saved["previous"] = os.environ.get(kill_switch.ENV_PATH)
    os.environ[kill_switch.ENV_PATH] = str(Path(directory.name) / "kill-switch.jsonl")


def tearDownModule():
    previous = _saved.pop("previous", None)
    if previous is None:
        os.environ.pop(kill_switch.ENV_PATH, None)
    else:
        os.environ[kill_switch.ENV_PATH] = previous
    _saved.pop("directory").cleanup()
