import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { dashboardRanges, getEquitySeries, positionPnl } from "./terminal";

describe("dashboard periods", () => {
  test("supports exactly 1D, 7D, 30D and YTD", () => {
    assert.deepEqual(dashboardRanges, ["1D", "7D", "30D", "YTD"]);
  });
  test("period filters produce different equity histories with a common latest equity", () => {
    const histories = dashboardRanges.map(getEquitySeries);
    assert.equal(new Set(histories.map((s) => s[0]?.equity)).size, 4);
    for (const history of histories) {
      assert.equal(history[71]?.equity, 12483920);
      assert.equal(history.every((p) => p.drawdown <= 0), true);
    }
  });
});
test("unrealized profit follows long and short direction", () => {
  assert.equal(positionPnl({ side: "LONG", entry: 100, mark: 110, size: 2 }), 20);
  assert.equal(positionPnl({ side: "SHORT", entry: 100, mark: 110, size: 2 }), -20);
});
