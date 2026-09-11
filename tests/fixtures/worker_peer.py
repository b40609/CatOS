"""Fault-injection child, exclusively invoked by test_worker.py."""

import os
import sys
import time

from catos import ipc


def main(mode):
    if mode == "startup_hang":
        time.sleep(30)
    if "CATOS_FAKE_CREDENTIAL" in os.environ or "PYTHONPATH" in os.environ:
        raise RuntimeError("test sentinel leaked into child environment")
    if mode == "stderr":
        sys.stderr.buffer.write(b"x" * 262_144)
        sys.stderr.buffer.flush()
    reader, writer = sys.stdin.buffer, sys.stdout.buffer
    initial = ipc.read_frame_sync(reader)
    cp = initial["payload"]["checkpoint"]
    ipc.write_frame_sync(writer, ipc.envelope("initialized", initial["generation"],
                                             initial["seq"], {"checkpoint": cp}))
    while True:
        message = ipc.read_frame_sync(reader)
        if mode == "hang":
            time.sleep(30)
        if mode == "crash":
            os._exit(17)
        if mode == "corrupt":
            writer.write(b"oops")
            writer.flush()
            time.sleep(30)
        if mode == "truncated":
            writer.write(b"\x00\x00\x00\x20{}")
            writer.flush()
            os._exit(18)
        cfg = ipc.WorkerConfig.from_wire(cp["config"])
        previous = ipc.Checkpoint.from_wire(cp, cfg)
        bar, account, warmup = ipc.parse_event(message["payload"], previous)
        cp = ipc.Checkpoint(cfg, previous.event_seq + 1, bar.open_time_ms,
                            (*previous.closes, bar.close)[-2:]).to_wire()
        payload = dict(checkpoint=cp, ready=len(cp["closes"]) == 2,
                       target="0" if mode == "warmup_intent" or not warmup else None)
        response = ipc.envelope("result", message["generation"], message["seq"], payload)
        if mode == "wrong_generation":
            response["generation"] = "old"
        if mode == "wrong_seq":
            response["seq"] += 1
        if mode == "impersonate":
            response["bot_id"] = "other-bot"
        if mode == "none":
            payload["target"] = None
        ipc.write_frame_sync(writer, response)
        if mode == "duplicate":
            ipc.write_frame_sync(writer, response)


if __name__ == "__main__":
    main(sys.argv[1])
