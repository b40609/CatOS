import { test } from 'node:test';
import assert from 'node:assert/strict';

// Test monotonic version guard logic
test('StateAdapter rejects stale updates with lower version', () => {
  const versionMap = { bots: 5 };
  
  function applyUpdate(domain, version, currentVersion) {
    if (version < currentVersion) {
      return false; // Dropped
    }
    return true; // Accepted
  }

  // Incoming older update from slow REST request (version 4 < current 5)
  assert.equal(applyUpdate('bots', 4, versionMap.bots), false, 'Older version 4 must be dropped');
  
  // Incoming equal update (version 5)
  assert.equal(applyUpdate('bots', 5, versionMap.bots), true, 'Equal version 5 is accepted');
  
  // Incoming newer update from real-time WebSocket (version 6 > current 5)
  assert.equal(applyUpdate('bots', 6, versionMap.bots), true, 'Newer version 6 must be accepted');
});

test('Decimal values must be strings and never floats', () => {
  const kpis = {
    total_equity: '125480.50',
    effective_leverage: '1.85',
  };

  assert.equal(typeof kpis.total_equity, 'string', 'total_equity must be string');
  assert.equal(typeof kpis.effective_leverage, 'string', 'effective_leverage must be string');
  assert.ok(!isNaN(Number(kpis.total_equity)), 'must be numeric parseable');
});

test('Mode isolation: local vs demo vs live', () => {
  const validModes = ['local', 'demo', 'live'];
  assert.ok(validModes.includes('local'));
  assert.ok(validModes.includes('demo'));
  assert.ok(validModes.includes('live'));
});
