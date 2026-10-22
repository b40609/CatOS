# -*- coding: utf-8 -*-
"""
Helper script to update catOS-Frontend-Final files safely.
"""
import pathlib
import sys

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def update_state_js():
    p = FRONTEND_ROOT / 'js' / 'state.js'
    text = p.read_text(encoding='utf-8')
    text = text.replace("preset: 'muted_charcoal',", "preset: 'obsidian_oled',", 1)
    text = text.replace("a.preset || 'muted_charcoal'", "a.preset || 'obsidian_oled'", 1)
    p.write_text(text, encoding='utf-8')
    print("state.js updated.")

if __name__ == '__main__':
    update_state_js()
