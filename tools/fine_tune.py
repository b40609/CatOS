# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def fine_tune():
    # 1. 調整 dashboard.js 標題
    p_dash = FRONTEND_ROOT / 'js' / 'views' / 'dashboard.js'
    t_dash = p_dash.read_text(encoding='utf-8')

    old_title_wrap = """                  <div class="widget-box-header">
                    <div class="widget-title-wrap" style="flex:1; min-width:0; overflow:hidden;">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh" style="font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">:: ALLOCATION // 保證金與曝險</div>
                      <div class="th-dual-en" style="font-size:10px;">MARGIN & EXPOSURE ALLOCATION</div>
                    </div>"""

    new_title_wrap = """                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh" style="font-size:12px; white-space:nowrap; color:var(--text-primary); font-weight:600;">:: ALLOCATION // 帳戶保證金與曝險配置</div>
                    </div>"""

    if old_title_wrap in t_dash:
        t_dash = t_dash.replace(old_title_wrap, new_title_wrap, 1)

    t_dash = t_dash.replace('\r\n', '\n')
    p_dash.write_bytes(t_dash.encode('utf-8'))

    # 2. 調整 views.css 中心 HUD 字體
    p_css = FRONTEND_ROOT / 'css' / 'views.css'
    t_css = p_css.read_text(encoding='utf-8')

    old_hud_css = """.donut-center-label {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  letter-spacing: 0.05em;
  transition: color 0.15s ease;
}
.donut-center-val {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
  margin-top: 2px;
  letter-spacing: -0.02em;
  transition: color 0.15s ease;
}
.donut-center-sub {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--gold-primary);
  margin-top: 2px;
}"""

    new_hud_css = """.donut-center-label {
  font-size: 9px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  letter-spacing: 0.05em;
  transition: color 0.15s ease;
}
.donut-center-val {
  font-size: 12.5px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
  margin: 1px 0;
  letter-spacing: -0.02em;
  transition: color 0.15s ease;
}
.donut-center-sub {
  font-size: 9px;
  font-family: var(--font-mono);
  color: var(--gold-primary);
}"""

    if old_hud_css in t_css:
        t_css = t_css.replace(old_hud_css, new_hud_css, 1)

    t_css = t_css.replace('\r\n', '\n')
    p_css.write_bytes(t_css.encode('utf-8'))
    print("Fine-tuning completed.")

if __name__ == '__main__':
    fine_tune()
