# MVP2-0 — InteractiveBrowser Tool

> **Status:** spec only, not implemented. This is a single MVP2 sub-feature:
> the **Interactive Browser** — a tool that lets any worker (especially QA)
> act like a human browsing the web: open URLs, click buttons, scroll,
> read console errors, inspect network traffic, and (with confirmation)
> drive automatic debug loops.
>
> Other MVP2 sub-features (escalation, checkpointing, QA templates) live in
> separate docs.

---

## 1. What this is, in one sentence

A **Playwright-powered headless browser** that exposes a rich action set
(navigate, click, fill, scroll, read DOM, read console, read network,
screenshot) and can be called by any worker via the existing
`OpsAgent.dispatch()` API.

It **replaces** the existing `BrowserSessionProvider` (which is too weak
for QA use cases) and adds:
1. Structured return values (not just "wait for selector, read text")
2. Console + network capture
3. **Automatic debug loops** — when given a URL with errors, return a
   diagnostic report
4. **Write-operation safety** — destructive actions are gated by a
   confirm protocol

---

## 2. The actions

| Action | Args | Returns | Risk |
|---|---|---|---|
| `navigate(url)` | url | page metadata (title, final URL, status code) | low (read) |
| `snapshot()` | — | accessibility tree (Playwright's `accessibility.snapshot()`) | low (read) |
| `read_text(selector?)` | optional CSS | plain text content | low (read) |
| `read_html(selector?)` | optional CSS | innerHTML | low (read) |
| `screenshot(path?)` | optional file path | base64 PNG, or saved path | low (read) |
| `read_console()` | — | list of `{type, text, location}` since page load | low (read) |
| `read_network()` | — | list of `{method, url, status, request_body?, response_body?}` | low (read) |
| `click(selector)` | CSS | success/fail | **medium** (may submit forms, navigate) |
| `scroll(direction, amount)` | "up"/"down", px | new scroll position | low |
| `fill(selector, value)` | CSS, text | success/fail | **medium** (form input) |
| `submit(selector)` | CSS form selector | success/fail | **HIGH** (real side effect) |
| `wait_for(selector, timeout?)` | CSS, ms | success/timeout | low |
| `eval(js_expression)` | string | return value | **HIGH** (arbitrary JS) |
| `debug_report(url)` | url | structured diagnosis (see § 5) | low (read) |

---

## 3. Write-operation confirm protocol

Per the user's chosen policy (Q3 = C, request-grant分级):

- **GET, HEAD, OPTIONS** — auto-allowed (read-only by HTTP semantics)
- **Anything else (POST, PUT, PATCH, DELETE)**, plus `submit()`, `fill()`,
  and `eval()` on inputs — **must be confirmed**

**Mechanism:** the browser tool runs in two modes.

### Mode 1: `auto` (default for QA-only reads)

All read actions (`navigate`, `snapshot`, `read_*`, `screenshot`) execute
silently. Any write action **pauses and prints to console**:

```
[browser] About to: click "#checkout-submit"
          This will POST to https://shop.example.com/orders
          Confirm? [y/N] (timeout 60s):
```

If the user types `y` (or `yes`) within 60 seconds, the action proceeds.
Otherwise it aborts and returns a `{"status": "aborted", "reason": "timeout"}`.

In **non-interactive** contexts (CI, the 8-hour dream run), the default
is **deny** — write actions fail with a clear error, and the worker is
prompted to escalate to a human or a higher-tier worker (see
[TODO.md § 1.3 escalation](TODO.md#13-escalation-between-tiers)).

### Mode 2: `dry-run`

No actions touch the server. `navigate` and `read_*` work; `click`,
`fill`, `submit`, `eval` all return `{"status": "blocked", "reason":
"dry-run mode"}`. Useful for testing the QA worker's reasoning without
any real side effects.

### Mode 3: `allow-all` (explicit opt-in)

Set `BROWSE_MODE=allow-all` in the env. All actions execute without
prompt. **The user is responsible for the consequences.** Intended for
sandboxes / disposable test accounts only.

### Selecting a mode

```yaml
# agent-ops.yaml
browse:
  mode: auto            # auto | dry-run | allow-all
  confirm_timeout: 60   # seconds
  blocklist:            # never auto-execute these patterns
    - "*/checkout*"
    - "*/delete*"
    - "*/transfer*"
```

The `blocklist` is a list of glob patterns matched against the target
URL. Matches are always denied regardless of mode. Defense in depth.

---

## 4. The new provider

```python
# src/agent_ops/browse.py  (proposed shape)

class InteractiveBrowserProvider(WorkerProvider):
    """
    A Playwright-powered headless browser with rich actions and
    write-operation safety. See docs/MVP2-0.md.
    """

    async def execute(
        self, prompt: str, context: dict | None = None
    ) -> str:
        """
        The 'prompt' is a JSON-encoded action spec:
            {"action": "navigate", "url": "https://..."}
            {"action": "click", "selector": "#submit"}
            {"action": "debug_report", "url": "https://..."}
        Returns a JSON-encoded result.
        """
        ...

    async def health_check(self) -> bool:
        # playwright importable? browser binaries installed?
        ...
```

Registered as `browse` in the `PROVIDERS` dict. The old `browser`
provider is **kept** for one release, marked deprecated, then removed.

### Auto-injection into other workers' prompts

When any worker has `browse` registered, `OpsAgent.dispatch()` will
prepend a hint to the worker's prompt:

```
You have access to an Interactive Browser. To use it, dispatch a
browse action via: dispatch("browse", <action-json>)
```

This means the QA worker doesn't need to know anything about the
browser — it just calls `ops.dispatch("browse", '{"action": "navigate", ...}')`
the same way it would call any other worker.

---

## 5. Automatic debug loop (`debug_report`)

The killer feature. Given a URL, the browser will:

1. Navigate.
2. Wait for `networkidle`.
3. Collect all `console.error` and `console.warn` messages.
4. Collect all 4xx/5xx network responses.
5. Take a screenshot.
6. **Read the page's stack trace** (if a JS error includes one).
7. Return a structured report:

```json
{
  "url": "https://app.example.com/checkout",
  "title": "Checkout — Acme",
  "status_code": 200,
  "console_errors": [
    {"text": "Uncaught TypeError: cart is null",
     "location": "https://app.example.com/static/cart.js:42:11"}
  ],
  "console_warnings": [
    {"text": "React: Each child in a list should have a unique key prop"}
  ],
  "failed_requests": [
    {"method": "POST", "url": "/api/orders", "status": 500,
     "response_body": "{\"error\": \"db timeout\"}"}
  ],
  "screenshot_b64": "iVBORw0KGgo...",
  "diagnosis": "JS error in cart.js:42 — 'cart' variable is null.
                Likely cause: cart state not loaded before render.
                Suggested fix: add null check or guard with
                useEffect that loads cart on mount."
}
```

The `diagnosis` field is generated by passing the collected signals to
an LLM (the QA worker, by default). The LLM returns a plain-English
explanation + fix suggestion. This is the **headline feature** that
makes QA actually useful for the 8-hour dream.

---

## 6. Migration from `BrowserSessionProvider`

The old `BrowserSessionProvider` is too weak to keep around. Migration:

| Step | What changes |
|---|---|
| 1. Land `InteractiveBrowserProvider` as `browse` | New code, doesn't affect anything |
| 2. Deprecate `BrowserSessionProvider` | Add a `DeprecationWarning` when `provider: browser` is used, point to `browse` |
| 3. Update `agent-ops.yaml` and README | Replace `browser` with `browse` in all examples |
| 4. One release later, remove the old provider | Delete the file, remove from `PROVIDERS` dict |

The new provider **subsumes** all the old one's functionality (and
more), so the migration is purely a name change plus a richer action
set.

---

## 7. Open questions

1. **Browser binary management.** Playwright needs to install browser
   binaries on first use (`playwright install chromium`). This is a
   ~300MB download. Should we ship it as a separate optional dep
   `agent-ops[browse]` so users who don't need it don't pay the cost?

2. **Session persistence.** Should the browser keep cookies / localStorage
   across calls (so the QA worker can log in once and stay logged in)?
   Probably yes for MVP2, but it means long-lived browser contexts and
   resource cleanup. Tracked separately.

3. **Multiple tabs.** For complex debug flows, you sometimes need two
   tabs open (e.g. log a user in, then in another tab act as that user).
   MVP2 keeps it to one tab; multi-tab is a P3 feature.

4. **LLM for `diagnosis`.** The `debug_report` action needs an LLM to
   write the plain-English diagnosis. Which LLM? Options:
   - The worker's own provider (re-dispatch to the same role)
   - A separate "diagnostician" worker
   - The user-configured default LLM (new `agent_ops.config.default_llm`)

   I recommend **the worker's own provider** for MVP2 — simplest, no new
   config knob.

5. **What if Playwright can't load the page?** (e.g. SSL error, infinite
   loading, Chrome crashes.) The action should return
   `{"status": "load_failed", "reason": "..."}` and the worker should
   escalate, not retry forever. Add a max-attempt cap (default: 2).

---

## 8. Implementation plan

| Sub-task | Estimated time |
|---|---|
| `browse.py` — provider skeleton + `navigate`/`snapshot`/`read_*` | 3 hours |
| `browse.py` — `click`/`fill`/`scroll` with confirm protocol | 2 hours |
| `browse.py` — `read_console` + `read_network` capture | 2 hours |
| `browse.py` — `debug_report` (collect + LLM diagnosis) | 3 hours |
| `browse.py` — `screenshot` | 30 min |
| `browse.py` — `eval` + `submit` with safety | 1 hour |
| Auto-injection into worker prompts | 1 hour |
| `agent-ops.yaml` mode/blocklist config plumbing | 1 hour |
| Tests (mocked Playwright responses) | 3 hours |
| Update README + docs | 1 hour |
| **Total** | **~17 hours (~2 working days)** |

---

## 9. Acceptance criteria (for "MVP2-0 is done")

A simple smoke test:

```bash
# Given a broken local HTML file:
echo '<script>throw new Error("boom")</script>' > /tmp/broken.html

# Run the QA worker against it:
python -c "
from agent_ops import OpsAgent
ops = OpsAgent()
ops.register_worker('qa', provider='copilot', model='gpt-4o-mini')
ops.register_worker('browse', provider='browse')
result = await ops.dispatch('browse', json.dumps({
    'action': 'debug_report',
    'url': 'file:///tmp/broken.html'
}))
print(result)
"
# Expected output: a JSON report with console_errors containing "boom"
# and a diagnosis explaining it's a script-thrown error.
```

If the report comes back with `console_errors: []`, MVP2-0 is **not**
done — Playwright is suppressing the error somehow.
