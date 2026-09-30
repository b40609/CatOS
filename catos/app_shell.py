"""Unified localhost application shell and read-only strategy status projection."""

from collections.abc import Callable, Mapping


def supervisor_status_provider(supervisor) -> Callable[[], dict]:
    """Return a read-only snapshot provider for an existing LocalSupervisor."""

    def snapshot():
        worker = getattr(supervisor, "_worker", None)
        process = getattr(worker, "process", None)
        worker_running = worker is not None and (
            process is None or getattr(process, "returncode", None) is None
        )
        checkpoint = getattr(supervisor, "checkpoint", None)
        return {
            "status": "materialized_read_only",
            "lifecycle_owner": "backend_supervisor",
            "browser_controls_lifecycle": False,
            "bot_id": getattr(supervisor, "bot_id", None),
            "health": getattr(supervisor, "health", None),
            "revision": getattr(supervisor, "revision", None),
            "event_seq": getattr(checkpoint, "event_seq", None),
            "worker_running": worker_running,
            "halt_reasons": sorted(getattr(supervisor, "halt_reasons", ())),
            "failure": getattr(supervisor, "failure", None),
        }

    return snapshot


def read_strategy_status(provider=None):
    """Normalize an optional read-only strategy status provider."""
    base = {
        "contract": "catos-strategy-status-v1",
        "lifecycle_owner": "backend_supervisor",
        "browser_controls_lifecycle": False,
        "mutation_routes": [],
    }
    if provider is None:
        return {
            **base,
            "status": "not_materialized",
            "bot_id": None,
            "health": None,
            "revision": None,
            "event_seq": None,
            "worker_running": None,
            "halt_reasons": [],
            "failure": None,
        }
    payload = provider()
    if not isinstance(payload, Mapping):
        raise TypeError("strategy_status_provider must return a mapping")
    return {**base, **dict(payload), "mutation_routes": []}


def _render_legacy_app_shell():
    return r'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>catOS · 量化交易 / Yaozi 情報</title>
<style>
:root{color-scheme:dark;--bg:#080706;--panel:#12100d;--line:#2d2822;--text:#ece7df;--muted:#8f877d;--gold:#c8a66d}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:var(--bg);color:var(--text);font:14px/1.5 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif}
body{display:grid;grid-template-rows:58px 1fr;overflow:hidden}.top{display:flex;align-items:center;border-bottom:1px solid var(--line);background:#0b0908;padding:0 22px;gap:24px}.brand{font:700 17px Georgia,"Noto Serif TC",serif}.brand small{display:block;color:var(--muted);font:700 8px system-ui,sans-serif;letter-spacing:.18em}.tabs{display:flex;height:100%;align-items:stretch;gap:4px}.tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:#a79d91;padding:0 22px;font-weight:700;cursor:pointer}.tabs button.active{color:var(--gold);border-bottom-color:var(--gold);background:#15110d}.meta{margin-left:auto;color:var(--muted);font-size:10px}.surface{width:100%;height:100%;border:0;background:var(--bg)}
</style>
</head>
<body>
<header class="top"><div class="brand">catOS<small>SINGLE LOCALHOST PRODUCT</small></div><nav class="tabs" aria-label="catOS top-level navigation"><button id="quantTab" class="active" data-route="/quant" onclick="openSurface('/quant','quant')">量化交易</button><button id="yaoziTab" data-route="/dashboard" onclick="openSurface('/dashboard','yaozi')">Yaozi 情報</button></nav><div class="meta">strategy lifecycle = backend Supervisor · browser navigation is read-only</div></header>
<iframe id="surface" class="surface" title="catOS surface" src="/quant"></iframe>
<script>
const frame=document.getElementById('surface');
function openSurface(route,key){frame.src=route;document.getElementById('quantTab').classList.toggle('active',key==='quant');document.getElementById('yaoziTab').classList.toggle('active',key==='yaozi');history.replaceState(null,'','#'+key)}
const initial=location.hash==='#yaozi'?['/dashboard','yaozi']:['/quant','quant'];openSurface(initial[0],initial[1]);
</script>
</body>
</html>'''


def _render_legacy_quant_surface(status):
    def text(value):
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    halts = ", ".join(status.get("halt_reasons") or ()) or "—"
    rows = [
        ("STATUS", status.get("status")),
        ("HEALTH", status.get("health")),
        ("BOT", status.get("bot_id")),
        ("REVISION", status.get("revision")),
        ("EVENT SEQ", status.get("event_seq")),
        ("WORKER RUNNING", status.get("worker_running")),
        ("HALT REASONS", halts),
        ("FAILURE", status.get("failure")),
    ]
    cards = "".join(
        f'<div class="card"><span>{label}</span><strong>{text(value)}</strong></div>'
        for label, value in rows
    )
    return f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>catOS · 量化交易</title><style>
:root{{color-scheme:dark;--bg:#080706;--panel:#12100d;--line:#302820;--text:#eee9e1;--muted:#91877c;--gold:#c9a66d}}*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;background:radial-gradient(circle at 30% -20%,#21170e 0,#090706 45%);color:var(--text);font:14px/1.5 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif}}main{{max-width:1180px;margin:0 auto;padding:54px 28px}}.eyebrow{{color:var(--gold);font-size:10px;letter-spacing:.25em}}h1{{font:italic 42px/1.05 Georgia,"Noto Serif TC",serif;margin:7px 0 10px}}p{{color:var(--muted);max-width:760px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:28px}}.card{{border:1px solid var(--line);background:rgba(18,16,13,.9);padding:15px;min-height:84px}}.card span{{display:block;color:var(--muted);font-size:9px;letter-spacing:.14em}}.card strong{{display:block;margin-top:8px;font-size:16px;word-break:break-word}}.contract{{margin-top:20px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:11px;line-height:1.8}}@media(max-width:820px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main><div class="eyebrow">QUANT · BACKEND-OWNED LIFECYCLE</div><h1>量化交易</h1><p>此頁只投影既有 Supervisor 狀態。瀏覽器切頁、重新整理與關閉頁面不會啟動、停止或重建策略；目前未物化 Web start/stop 控制。</p><section class="grid">{cards}</section><div class="contract">contract={text(status.get('contract'))}<br>lifecycle_owner={text(status.get('lifecycle_owner'))}<br>browser_controls_lifecycle={text(status.get('browser_controls_lifecycle'))}<br>mutation_routes=[]</div></main></body></html>'''


def render_app_shell():
    """Render the current localhost product shell prototype."""
    return render_workbench_surface("/")


def render_workbench_surface(initial_path="/app/dashboard"):
    """Render the browser-only multi-page workbench prototype."""
    from catos.workbench_prototype import render_workbench_prototype

    return render_workbench_prototype(initial_path)


def render_quant_surface(status):
    """Render the browser-only quant research prototype.

    ``status`` stays in the signature so the existing read-only lifecycle
    projection contract remains available through /system/strategy-status.
    The prototype itself intentionally does not mutate or consume it.
    """
    del status
    from catos.quant_prototype import render_quant_prototype

    return render_quant_prototype()


def render_yaozi_placeholder():
    from catos.quant_prototype import render_yaozi_placeholder as render

    return render()
