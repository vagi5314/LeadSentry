# LeadSentry Pro — Brutal Engineering Audit

**Auditor:** Senior Engineer  
**Date:** 2026-06-09  
**Severity:** CRITICAL / HIGH / MEDIUM / LOW  
**Status:** 27 issues found — 6 CRITICAL, 9 HIGH, 8 MEDIUM, 4 LOW

---

## CRITICAL — System Breaks or Corrupts Data

### C1. `$json` in Code Node Fails in "Run Once for All Items" Mode
**Node:** `Format Error Response` (errResp)  
**Code:** `const warnings = $json.warnings || [];`  
**Problem:** n8n Code nodes default to "Run Once for All Items" mode. In this mode, `$json` is undefined — only `$input.all()` works. The error response will crash with `Cannot read property 'warnings' of undefined`.  
**Impact:** Every invalid lead gets a 500 error instead of 400.  
**Fix:** Change to `$input.first().json.warnings` or switch the node to "Run Once for Each Item" mode.

### C2. No `onError` on Any Code Node — One Crash Kills the Entire Workflow
**Nodes:** Validate Input, Enrich Lead Data, Score Lead, Format Error Response  
**Problem:** None have `onError: "continueErrorOutput"` or `"continueRegularOutput"`. If ANY Code node throws (bad data, undefined property, stack overflow), the entire execution dies with a 500.  
**Impact:** One malformed lead request kills the workflow. No response sent to caller.  
**Fix:** Add `onError: "continueErrorOutput"` + error handler node to all Code nodes.

### C3. Webhook Has No `onError` Config — Crashes Without Response
**Node:** Receive Lead (wh)  
**Problem:** The webhook node has no error handling. If downstream nodes fail, the webhook never sends a response. The caller hangs until timeout.  
**Impact:** Callers get connection timeout (no HTTP response).  
**Fix:** Add `"options": {"onError": "continueRegularOutput"}` to webhook.

### C4. Telegram Fails = Entire Lead Lost
**Nodes:** Telegram: Hot Alert (tgHot), Telegram: Quiet Digest (tgOther)  
**Problem:** Telegram nodes are in the main flow before Respond Success. If Telegram API is down, rate-limited, or chat ID is wrong, the execution fails BEFORE the response is sent. The lead is lost — not scored, not logged, not responded.  
**Impact:** During Telegram outage, ALL hot/warm leads are silently dropped.  
**Fix:** Telegram should be a fire-and-forget branch AFTER Respond Success, or use `onError: "continueRegularOutput"`.

### C5. Email Validation Accepts Garbage
**Node:** Validate Input  
**Code:** `!input.email.includes('@')`  
**Impact Accepted:**
- `@domain.com` → valid (no local part)
- `user@` → valid (no domain)
- `a@b` → valid (no TLD)
- `@@@` → valid (contains @)
- `" "@domain.com` → valid (spaces in local)
- `user@domain.c` → valid (1-char TLD)  
**Impact:** Spam/junk leads pass validation, pollute scoring.  
**Fix:** Use regex: `/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/`

### C6. Phone Validation — Single Digit Passes
**Node:** Validate Input  
**Code:** `phone: (input.phone || '').replace(/[^0-9+\-\s()]/g,'').substring(0, 20) || null`  
**Problem:** A phone like `"5"` becomes `"5"` (not null). Then in Enrich: `e.hasPhone = !!d.phone && d.phone.length >= 7` — length 1 < 7, so `hasPhone = false`. BUT the sanitized phone is still `"5"` (not null), so downstream code might treat it as "has phone".  
**Impact:** Lead has `phone: "5"` — looks like it has a phone, but scoring says no phone. Data inconsistency.  
**Fix:** After sanitization, if length < 7, set phone to null.

---

## HIGH — Incorrect Behavior / Data Integrity

### H1. `raw.body || raw` — Array/Primitive Input Bypasses Validation
**Node:** Validate Input  
**Code:** `const input = raw.body || raw;`  
**Problem:** If the webhook receives `[]` (array), `raw.body` is undefined, so `input = []`. Then `input.name` is undefined. Errors are pushed. BUT `input` is still `[]` — an array. When we later do `return [{ json: { ...sanitized } }]`, the response structure might confuse downstream nodes expecting an object.  
**Impact:** Edge case: array payloads cause unexpected shapes.  
**Fix:** Add type check: `if (!input || typeof input !== 'object' || Array.isArray(input))` → error.

### H2. `parseInt` on Budget — Unexpected Coercion
**Node:** Validate Input  
**Code:** `budget: (() => { const b = parseInt(input.budget); return (!isNaN(b) && b >= 0) ? b : null; })()`  
**Problems:**
- `"15000abc"` → `15000` (trailing garbage silently ignored)
- `"abc15000"` → `NaN` (leading garbage rejected — inconsistent)
- `"15,000"` → `15` (comma causes truncation!)
- `"0x1F4"` → `500` (hex parsed as decimal)
- `"  15000  "` → `15000` (fine, but surprising)  
**Impact:** Budget of `"15,000"` becomes `15`. Scoring uses 15 instead of 15000.  
**Fix:** Use `Number(input.budget)` or strip commas before parseInt.

### H3. Description Quality = Purely Length-Based
**Node:** Enrich Lead Data  
**Code:** `e.descriptionQuality = descLen < 30 ? 'poor' : descLen < 100 ? 'minimal' : ...`  
**Problem:** A 300-char description of "aaaaaaa..." scores `decent` (12 pts). A 200-char detailed brief scores `minimal` (5 pts). No semantic analysis.  
**Impact:** Gaming the system: pad descriptions with spaces/repeated chars to inflate score.  
**Fix:** Add word count, unique word ratio, or keyword density as secondary signal.

### H4. Requirements Detection — Keyword-Only, False Positives
**Node:** Enrich Lead Data  
**Code:** `const keywords = ['urgent','asap','deadline','need ','require','must have','looking for','budget','timeline','start date','immediately','by the','done by','complete by','finish by'];`  
**Problems:**
- `"need "` (with trailing space) — won't match `"needs"` or `"needed"`
- `"by the"` — matches `"by the way"` (not a deadline signal)
- `"require"` — matches `"requirement"` (fine) but also `"requires"` (fine)
- `"budget"` — matches "what's your budget?" (question, not a signal)
- No negative signals: "no deadline", "not urgent", "flexible timeline"  
**Impact:** False positive requirement detection inflates score by 10 pts.  
**Fix:** Use word boundaries `\b`, add negative keywords, weight by context.

### H5. Source Quality Weights — `source * 0.15` Can Exceed Breakdown Max
**Node:** Score Lead  
**Code:** `b.source = Math.round(e.sourceQuality * 0.15);`  
**Problem:** `referral: 90 * 0.15 = 13.5 → 14`. But `b.source` is supposed to be one component of a 0-100 score. With 8 components, if each averages 12.5, total is 100. But source alone can be 14, meaning other components must be lower to compensate. The breakdown is NOT normalized.  
**Impact:** Enterprise + referral leads can score 104 before cap. The cap hides overflow.  
**Fix:** Normalize breakdown so total max = 100 without relying on cap.

### H6. Lead ID — Not Globally Unique
**Node:** Validate Input  
**Code:** `'ls_' + Date.now().toString(36) + Math.random().toString(36).substr(2,6)`  
**Problem:** `Date.now()` has millisecond resolution. Two requests in the same ms get the same timestamp. The random suffix is 6 chars of base36 = ~2.1M possible values. Under high load (1000+ req/sec), collision probability is non-trivial.  
**Impact:** Duplicate lead IDs → dedup logic (if added later) would merge distinct leads.  
**Fix:** Use `crypto.randomUUID()` or add process-level counter.

### H7. Warnings Array Mutated Across Nodes — Duplicate Warnings
**Nodes:** Enrich Lead Data + Validate Input  
**Problem:** Validate Input initializes `warnings = []`. Enrich pushes more warnings. If the workflow is modified to add another warning node, the array could have duplicates. Also, the warnings are not deduped.  
**Impact:** Duplicate warnings in response (cosmetic, but sloppy).  
**Fix:** Deduplicate: `[...new Set(warnings)]` before return.

### H8. Respond Success Body Uses Expression — Crash on Missing Fields
**Node:** Respond Success  
**Code:** `={{ (function() { const d = $input.first().json; return { ... score: d.score.total, ... warnings: d.warnings || [], ... }; })() }}`  
**Problem:** If any upstream node silently drops `score` or `warnings` from the data (e.g., a node error that partially passes), `d.score.total` throws `Cannot read property 'total' of undefined`. The expression evaluation crashes.  
**Impact:** 500 error on response even though lead was processed.  
**Fix:** Add null checks: `d.score?.total ?? 0`, `d.warnings ?? []`.

### H9. `Is Hot/Warm?` Condition — Only Checks Priority ≤ 2
**Node:** Is Hot/Warm?  
**Code:** `rightValue: 2` with `lte` operator  
**Problem:** The condition routes `hot` (prio 1) and `warm` (prio 2) to the same path. But `cool` (prio 3) and `cold` (prio 4) go to the same quiet digest. There's no differentiation between cool and cold leads — they get the same Telegram message.  
**Impact:** Cool leads (worth following up) treated identically to cold leads (worthless).  
**Fix:** Add a third branch for cool leads, or adjust thresholds.

---

## MEDIUM — Performance / Maintenance / Security

### M1. No Rate Limiting on Webhook
**Problem:** Any client can flood the webhook with thousands of requests per second. Each request runs full enrichment + scoring + Telegram. Under DDoS, n8n exhausts resources.  
**Fix:** Add rate limiting at reverse proxy (nginx) or n8n middleware.

### M2. No Content-Type Validation
**Problem:** Webhook accepts `text/plain`, `application/xml`, `image/png` — any content type. The `raw.body` might be a string, buffer, or XML document.  
**Fix:** Add `"options": {"rawBody": false}` and validate Content-Type header.

### M3. 32MB Payload Limit Not Enforced at Workflow Level
**Problem:** `N8N_PAYLOAD_SIZE_MAX=32` (MB) is set in env, but the workflow doesn't check. A 32MB JSON body will be parsed and validated field-by-field before rejection.  
**Fix:** Add early size check or ensure n8n enforces before node execution.

### M4. Hardcoded Telegram Chat ID
**Node:** Telegram: Hot Alert, Telegram: Quiet Digest  
**Code:** `"chatId": "1794140046"`  
**Problem:** Changing the recipient requires editing the workflow. Can't route different lead categories to different chats.  
**Fix:** Use expression: `{{ $json.score.category === 'hot' ? 'CHAT_ID_1' : 'CHAT_ID_2' }}` or environment variable.

### M5. Hardcoded Personal Email List — Goes Stale
**Node:** Enrich Lead Data  
**Code:** `const personal = ['gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','protonmail.com','icloud.com','mail.com','yandex.com'];`  
**Problem:** Missing: `zoho.com`, `hey.com`, `fastmail.com`, `tutanota.com`, `gmx.com`, `live.com`, `msn.com`, `ymail.com`, `googlemail.com`. New providers emerge yearly.  
**Fix:** Use an external API or maintain a config file, not hardcoded array.

### M6. No Execution Logging / Audit Trail
**Problem:** n8n stores execution history, but the workflow doesn't log lead scores to a database or file. If n8n execution history is cleared, all lead data is lost.  
**Fix:** Add a "Log to Database/File" node after scoring.

### M7. No Idempotency — Duplicate Leads on Retry
**Problem:** If a caller retries a failed request, a new lead is created with a new ID. No dedup on email+timestamp.  
**Fix:** Check if same email was processed in last N minutes, return existing score.

### M8. Telegram Message Can Exceed 4096 Characters
**Node:** Telegram: Hot Alert  
**Problem:** The message includes name, email, company, budget, score, source, urgency, description (up to 200 chars), and lead ID. With max values, the message could exceed Telegram's 4096 char limit.  
**Impact:** Telegram API error → lead lost (see C4).  
**Fix:** Truncate description to 100 chars, or calculate total length before send.

---

## LOW — Code Quality / Future Risk

### L1. Outdated Node typeVersions
| Node | Current | Latest |
|------|---------|--------|
| Webhook | 1 | 2.1 |
| IF (Is Valid?) | 2 | 2.2 |
| IF (Is Hot/Warm?) | 2 | 2.2 |
| Respond to Webhook | 1.1 | 1.4 |
| Telegram | 1.1 | 1.2 |

**Risk:** Missing bug fixes and performance improvements. Future n8n versions may deprecate old types.

### L2. No Workflow-Level Timeout
**Problem:** If a Code node enters an infinite loop (unlikely but possible with bad data), the workflow hangs until `N8N_EXECUTIONS_TIMEOUT=900` (15 min).  
**Fix:** Set per-node timeout or reduce workflow timeout to 30s.

### L3. `binaryMode: "separate"` in Settings — Unused
**Problem:** The workflow sets `binaryMode: "separate"` but never handles binary data. Dead config.  
**Fix:** Remove from settings.

### L4. No Input Schema Validation
**Problem:** No JSON Schema or OpenAPI spec defined for the webhook. Callers don't know what fields are expected.  
**Fix:** Add webhook schema or create Postman collection.

---

## Summary by Node

| Node | Issues | Severities |
|------|--------|------------|
| Receive Lead (webhook) | C3, M1, M2, M3 | CRITICAL, MEDIUM×3 |
| Validate Input | C1, C5, C6, H1, H2, H6 | CRITICAL×2, HIGH×4 |
| Is Valid? | H9 | HIGH |
| Format Error Response | C1, C5 | CRITICAL×2 |
| Enrich Lead Data | H3, H4, H5, M5 | HIGH×4, MEDIUM |
| Score Lead | H5, H9 | HIGH×2 |
| Is Hot/Warm? | H9 | HIGH |
| Telegram: Hot Alert | C4, M4, M8 | CRITICAL, MEDIUM×2 |
| Telegram: Quiet Digest | C4, M4 | CRITICAL, MEDIUM |
| Respond Success | H8 | HIGH |
| Respond 400 | — | — |
| Global (infra) | C2, M6, M7, L1-L4 | CRITICAL, MEDIUM×3, LOW×4 |

---

## Recommended Fix Priority

1. **C1 + C2 + C3** — Error handling (prevents total workflow death)
2. **C4** — Telegram isolation (prevents lead loss during outage)
3. **C5** — Email validation (prevents garbage data entry)
4. **C6** — Phone sanitization (data consistency)
5. **H2** — Budget parsing (prevents scoring corruption)
6. **H8** — Null-safe response (prevents 500 on edge cases)
7. **H5** — Score normalization (prevents score inflation)
8. Everything else in priority order
