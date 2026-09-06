---
name: research
description: "背景調查與研究：針對第一手高信任來源進行深入調查，並將調查結果與引用來源輸出為 Markdown 檔案。Investigate a question against high-trust primary sources."
---

Spin up a **background agent** to do the research, so you keep working while it reads.

Its job:

1. Investigate the question against **primary sources** (official docs, source code, specs, first-party APIs), not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Write the findings to a single Markdown file, citing each claim's source.
3. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it in `docs/research/<topic>.md`.
