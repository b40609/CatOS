---
name: setup-catOS-skills
description: "專案設定：配置 catOS 專案的本地任務追蹤器（.scratch/）、領域文件（CONTEXT.md、docs/adr/）與規約。Configure this repo for engineering skills."
---

# Setup catOS Skills

Scaffold and maintain the per-repo configuration that the engineering skills assume:

- **Issue tracker**: Local Markdown files under `.scratch/`
- **Domain docs**: Single-context layout with `CONTEXT.md` at root and ADRs in `docs/adr/`
- **Project rules**: `AGENTS.md` and `.agents/rules/catOS-conventions.md`

## Configuration Summary

This repository is already configured with:

1. **Issue Tracker**: Local Markdown tracker (`docs/agents/issue-tracker.md`)
   - Specs live in `.scratch/<feature-slug>/spec.md`
   - Issues live in `.scratch/<feature-slug>/issues/<NN>-<slug>.md`
   - Maps live in `.scratch/<effort>/map.md`
2. **Domain Docs**: `docs/agents/domain.md`
   - `CONTEXT.md` at repo root defines the ubiquitous language
   - `docs/adr/` contains Architecture Decision Records
3. **Workflow Rules**: `AGENTS.md` and `.agents/rules/catOS-conventions.md`
   - Red lines (AI cannot place real orders, only OKX Demo live execution in v1, etc.)
   - Forbidden terminology vs Canonical terminology
   - Traditional Chinese output preference
