"""變異檢查：不改 catos/、tests/，在記憶體內換掉函式或模組原始碼後跑 MarginRatioTests。

用法（repo 根目錄、暫存家目錄）：
  T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe reports/margin-ratio-20261118/scratch/mutants.py <mutant>
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from catos import okx_demo  # noqa: E402
from catos.okx_demo import DemoClient, DemoError, _dec  # noqa: E402


def _rows(self):
    rows = self._request("GET", "/api/v5/account/balance", {"ccy": "USDT"})
    account = rows[0]
    usdt = next((d for d in account.get("details", []) if d.get("ccy") == "USDT"), None)
    if usdt is None or _dec(usdt, "eq") is None:
        raise DemoError("no usdt")
    return account, usdt


def snap(ratio_fn):
    def account_snapshot(self):
        account, usdt = _rows(self)
        return {"usdt_eq": _dec(usdt, "eq"), "mgn_ratio": ratio_fn(account, usdt),
                "u_time": int(account.get("uTime") or 0)}
    return account_snapshot


OKX_MUTANTS = {
    # 回到修正前：只讀帳戶層級
    "top_only": snap(lambda a, u: _dec(a, "mgnRatio")),
    # 只讀 details，忽略帳戶層級
    "details_only": snap(lambda a, u: _dec(u, "mgnRatio")),
    # 先讀 details 再退回帳戶層級（優先序顛倒）
    "details_first": snap(lambda a, u: _dec(u, "mgnRatio") if _dec(u, "mgnRatio") is not None else _dec(a, "mgnRatio")),
    # 兩處都沒有時當成安全（放寬）
    "missing_is_safe": snap(lambda a, u: _dec(a, "mgnRatio") or _dec(u, "mgnRatio") or okx_demo.Decimal("999")),
    # 取 details 的第一筆（不分幣種）
    "any_ccy": snap(lambda a, u: _dec(a, "mgnRatio") if _dec(a, "mgnRatio") is not None
                    else _dec((a.get("details") or [{}])[0], "mgnRatio")),
}

BOT_MUTANTS = {
    # 門檻放寬：任何正值都算安全
    "threshold_gt0": (">= 3)", "> 0)"),
    # 門檻收緊到 100（測試的 50 會被擋）
    "threshold_100": (">= 3)", ">= 100)"),
    # 不檢查 None（None >= 3 會丟 TypeError）
    "drop_none_check": ('(facts["mgn_ratio"] is not None and facts["mgn_ratio"] >= 3)', '(facts["mgn_ratio"] or 0) >= 3'),
    # 持倉一律安全
    "always_ok": ('margin_ok = facts["position"] == 0 or', 'margin_ok = True or'),
}


def main(name):
    if name in OKX_MUTANTS:
        DemoClient.account_snapshot = OKX_MUTANTS[name]
    elif name in BOT_MUTANTS:
        from catos import demo_bot
        old, new = BOT_MUTANTS[name]
        source = Path(demo_bot.__file__).read_text(encoding="utf-8")
        assert source.count(old) == 1, (name, source.count(old))
        exec(compile(source.replace(old, new), demo_bot.__file__, "exec"), demo_bot.__dict__)
    elif name != "baseline":
        raise SystemExit(f"unknown mutant {name}")
    import test_demo_bot
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_demo_bot.MarginRatioTests)
    result = unittest.TextTestRunner(stream=open("NUL" if sys.platform == "win32" else "/dev/null", "w"),
                                     verbosity=0).run(suite)
    failed = sorted({t.id().rsplit(".", 1)[-1] for t, _ in result.failures + result.errors})
    print(f"{name}: run={result.testsRun} failed={len(failed)} {'KILLED' if failed else 'SURVIVED'} {failed}")


if __name__ == "__main__":
    main(sys.argv[1])
