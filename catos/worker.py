"""Child-only strategy runner. No credentials, trading client or persistence."""

import sys

from catos import ipc, research
from examples.sma_state import restore_sma, snapshot_closes


def run(reader, writer):
    message = ipc.read_frame_sync(reader)
    ipc.exact(message, ("version", "kind", "generation", "seq", "payload"))
    generation = ipc.token(message["generation"], "generation")
    seq = ipc.integer(message["seq"], "seq")
    payload = ipc.check_envelope(message, "init", generation, seq)
    require_ack = payload.get("commit_ack", False)
    if type(require_ack) is not bool:
        raise ipc.ProtocolError("commit_ack must be bool")
    ipc.exact(payload, ("config", "checkpoint", "commit_ack") if "commit_ack" in payload else ("config", "checkpoint"))
    config = ipc.WorkerConfig.from_wire(payload["config"])
    checkpoint = ipc.Checkpoint.from_wire(payload["checkpoint"], config)
    if seq != checkpoint.event_seq:
        raise ipc.ProtocolError("init sequence/checkpoint mismatch")
    strategy = restore_sma(checkpoint)
    expected_source = None
    if config.strategy_artifact is not None:
        from catos.research_catalog import provenance

        expected_source = provenance()
    ipc.write_frame_sync(writer, ipc.envelope("initialized", generation, seq,
                                             {"checkpoint": checkpoint.to_wire()}))
    while True:
        message = ipc.read_frame_sync(reader)
        payload = ipc.check_envelope(message, "bar", generation, checkpoint.event_seq + 1)
        bar, account, warmup = ipc.parse_event(payload, checkpoint)
        if expected_source is not None and provenance() != expected_source:
            raise ipc.ProtocolError("source_changed_during_local_sim")
        if research._call(strategy.update_indicators, bar) is not None:
            raise ipc.ProtocolError("indicator update must not produce an intent")
        ready = research._ready(strategy)
        if (not warmup or checkpoint.event_seq + 1 == config.warmup_bars) and not ready:
            raise ipc.ProtocolError("strategy not ready at evaluation boundary")
        target = None if warmup else research._call(strategy.on_bar, bar, account)
        if target is not None:
            research._decimal(target, "target_position")
        next_checkpoint = ipc.Checkpoint(config, checkpoint.event_seq + 1,
                                         bar.open_time_ms, snapshot_closes(strategy))
        result = dict(target=None if target is None else str(target),
                      checkpoint=next_checkpoint.to_wire(), ready=ready)
        ipc.parse_result(result, checkpoint, bar, account, warmup)
        if expected_source is not None and provenance() != expected_source:
            raise ipc.ProtocolError("source_changed_during_local_sim")
        ipc.write_frame_sync(writer, ipc.envelope("result", generation,
                                                 next_checkpoint.event_seq, result))
        if require_ack:
            acknowledgement = ipc.read_frame_sync(reader)
            ipc.exact(ipc.check_envelope(acknowledgement, "ack", generation,
                                        next_checkpoint.event_seq), ())
            ipc.write_frame_sync(writer, ipc.envelope("acknowledged", generation,
                                                     next_checkpoint.event_seq, {}))
        checkpoint = next_checkpoint


def main():
    try:
        run(sys.stdin.buffer, sys.stdout.buffer)
    except Exception as exc:
        print(f"{type(exc).__name__}: {str(exc)[:512]}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
