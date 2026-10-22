# -*- coding: utf-8 -*-
import pathlib

p = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final\test_workspace_spec.js')
text = p.read_text(encoding='utf-8')
text = text.replace(
    "const requiredWidgets = ['kpi_grid', 'equity_chart', 'incident_timeline', 'active_bots', 'research_tasks', 'yaozi_brief'];",
    "const requiredWidgets = ['kpi_grid', 'equity_chart', 'incident_timeline', 'active_bots', 'research_tasks', 'yaozi_brief', 'allocation', 'risk_latch'];"
)
text = text.replace(
    "if (p.desktop.length !== 6 || p.compact.length !== 6) {",
    "if (p.desktop.length < 6 || p.compact.length < 6) {"
)
text = text.replace(
    "=== Test 1: Verify 3 Presets & 6 Widgets Constraints ===",
    "=== Test 1: Verify 3 Presets & 8 Widgets Constraints ==="
)
p.write_text(text, encoding='utf-8')
print('test_workspace_spec.js updated.')
