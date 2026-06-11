# AgentOps TODO

## [ ] Voice → Prompt Optimizer Module

**Goal:** Speak → STT → auto-optimize into structured prompt → send to agent

**Key features:**
- Voice-to-text input (iOS dictation)
- Preserve original spoken text (for reference)
- Auto-optimize colloquial text into clear, structured prompts
- Mainly for: UX design changes, critical issue reports

**Components needed:**
1. `prompt_optimizer.py` — takes messy spoken text, outputs structured prompt
2. iOS Shortcut config — Dictate → call optimizer → send to agent
3. Consider: keep original text alongside optimized version

**Why:** Typing long prompts on iPhone is painful. Voice + auto-optimization = fast iteration.

**Status:** Backlogged — do later