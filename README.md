# LeadSentry

**Enterprise-grade inbound lead qualifier built on [n8n](https://n8n.io). Receives leads via webhook, validates, scores on two axes, extracts BANT, routes by tier, and alerts — end-to-end in under 500 ms.**

![n8n](https://img.shields.io/badge/n8n-2.21.7-FF6D5B?logo=n8n&logoColor=white)
![Nodes](https://img.shields.io/badge/nodes-31-1f6feb)
![Tests](https://img.shields.io/badge/tests-100%2F100-2ea043)
![Latency](https://img.shields.io/badge/avg%20latency-440%E2%80%93505%20ms-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## What it does

A single webhook call returns a fully scored, BANT-tagged, tier-routed lead — plus an optional Telegram alert for hot/warm leads. The pipeline gates every inbound lead through five defensive layers before scoring:

```
Receive → HMAC Verify → Rate Limit → Idempotency → Bot/Spam Filter
   → Validate & Sanitize → Enrich → Score (dual-axis) → Route (BANT tiers)
   → Respond → Telegram (when composite ≥ 40)
```

A separate **error-handler workflow** funnels node failures into a Telegram dead-letter queue, and a scheduled **SLA monitor** raises alerts when response time breaches the configured threshold.

---

## Key metrics

| | |
|---|---|
| Nodes | 31 |
| Connections | 26 |
| Test coverage | 100 / 100 |
| Avg response | 440–505 ms |
| n8n version | 2.21.7 (Docker) |
| Webhook | `POST /webhook/leadsentry-v4` |

---

## Architecture

```
                          ┌─────────────────────────────────────────────┐
                          │           ERROR HANDLER (separate)          │
                          │  Error Trigger → Log Error → Build DLQ     │
                          │                               ↓            │
                          │                     DLQ Telegram Alert      │
                          └─────────────────────────────────────────────┘

                          ┌─────────────────────────────────────────────┐
                          │           SLA MONITOR (scheduled)           │
                          │  SLA Monitor → SLA Check → Build SLA Alert │
                          │       ↓                    ↓               │
                          │  Has SLA Breaches?    No SLA Breach        │
                          │    ↓                        (noop)         │
                          │  SLA Breach Alert                          │
                          │    (telegram)                              │
                          └─────────────────────────────────────────────┘

┌──────────┐    ┌────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐
│ Receive  │───▶│ HMAC   │───▶│ Rate     │───▶│ Idempot. │───▶│ Bot & Spam │
│ Lead     │    │ Verify │    │ Limit    │    │ Gate     │    │ Filter     │
│ (webhook)│    │ (code) │    │ Check    │    │ (code)   │    │ (code)     │
└──────────┘    └────────┘    └──────────┘    └──────────┘    └─────┬──────┘
                                                                     │
                                                              ┌──────▼──────┐
                                                              │  Is Spam?   │
                                                              │  (IF node)  │
                                                              └──┬───────┬──┘
                                                    TRUE ↓          ↓ FALSE
                                                  ┌──────────┐  ┌────────────────┐
                                                  │ Reject   │  │ Validate &     │
                                                  │ Spam 400 │  │ Sanitize       │
                                                  └──────────┘  └───────┬────────┘
                                                                         │
                                                                  ┌──────▼──────┐
                                                                  │  Is Valid?  │
                                                                  │  (IF node)  │
                                                                  └──┬───────┬──┘
                                                    TRUE ↓          ↓ FALSE
                                                  ┌──────────┐  ┌──────────────┐
                                                  │ Enrich   │  │ Respond      │
                                                  │ Lead     │  │ 400          │
                                                  └────┬─────┘  └──────────────┘
                                                       │
                                                  ┌────▼─────┐
                                                  │ Score    │  (Fit 0-100 + Intent 0-100)
                                                  │ Lead     │  → compositeScore
                                                  └────┬─────┘
                                                       │
                                                  ┌────▼─────┐
                                                  │ Route    │  (A hot / B warm / B promising /
                                                  │ Lead     │   C nurture / C low_intent / D cold)
                                                  └────┬─────┘
                                                       │
                                                  ┌────▼─────┐    ┌──────────────┐
                                                  │ Build    │───▶│ Respond      │
                                                  │ Response │    │ Success 200  │
                                                  └────┬─────┘    └──────────────┘
                                                       │
                                                  ┌────▼──────────┐
                                                  │ Needs         │
                                                  │ Notification? │
                                                  └──┬─────────┬──┘
                                          composite ≥ 40 │      │ < 40
                                                     ┌────▼────┐ ┌────────┐
                                                     │ Build TG│ │ No     │
                                                     │ Message │ │ Notif. │
                                                     └────┬────┘ └────────┘
                                                     ┌────▼────┐
                                                     │ Telegram│
                                                     │  Alert  │
                                                     └─────────┘
```

Full node-by-node breakdown, the scoring model, BANT extraction, and the security layer rationale live in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Scoring model

Two independent axes, averaged into a composite:

| Axis | Range | Components |
|---|---|---|
| **Fit** | 0–100 | Email quality (25) · Company (15) · Role/seniority (25) · Company size (20) · Contact completeness (15) |
| **Intent** | 0–100 | Budget signal (25) · Urgency (20) · Description quality (20) · Pain signals (15) · Decision authority (10) · Source quality (10) |
| **Composite** | 0–100 | `0.5 * fit + 0.5 * intent` |

Routing tiers:

| Tier | Category | Rule | Action |
|---|---|---|---|
| A | hot | composite ≥ 70 AND intent ≥ 60 | Immediate outreach |
| B | warm | composite ≥ 60 OR intent ≥ 70 | Qualify & nurture |
| B | promising | composite ≥ 40 AND intent ≥ 60 | Discovery call |
| C | nurture | composite ≥ 40 OR intent ≥ 20 | Drip campaign |
| C | low_intent | composite ≥ 40 AND intent < 20 | Re-engage |
| D | cold | composite < 40 AND intent < 20 | Archive |

A separate BANT pass extracts **Budget · Authority · Need · Timeline** from the lead's free-text description and returns them on the response payload.

---

## Project structure

```
.
├── leadsentry_v4.json           # The workflow — import into n8n
├── build_v4.py                  # Workflow-as-code builder (source of truth)
├── test_v4.py                   # Main test suite — 100 cases
├── test_v4_comprehensive.py     # Extended + deployment verification
├── test_v4_final.py             # Final smoke tests against deployed flow
├── stress_test_v4.py            # Stress / edge-case harness
├── brutal_test.py               # Brute-force input fuzzing
├── e2e_test_v3.py               # End-to-end driver
├── ARCHITECTURE.md              # Node-by-node reference, scoring model, security layers
├── AUDIT_REPORT.md              # 27-issue engineering audit (6 CRITICAL / 9 HIGH / 8 MEDIUM / 4 LOW)
├── V5_UPGRADE_PLAN.md           # Planned v5 — AI scoring, enrichment APIs, persistence
└── SESSION_HANDOFF.md           # Build log: IF-node bug fix, n8n downgrade, error-handler wiring
```

Scratch debug scripts, older workflow snapshots, execution dumps, and screenshots are kept locally but excluded from the repo via `.gitignore`.

---

## Tech stack

| Layer | Stack |
|---|---|
| Orchestrator | [n8n](https://n8n.io) 2.21.7 (Docker) — Code, IF, Webhook, Telegram, Error Trigger, Schedule Trigger nodes |
| Logic | 15 in-workflow Code nodes (JavaScript) — HMAC, rate limit, idempotency, spam, validation, enrichment, scoring, routing, response shaping |
| Alerting | Telegram Bot API (n8n native node) |
| Tests | Python 3.10+ (`requests`) — 100-case suite + stress + brute-force + E2E |
| Docs | Markdown — architecture, audit, v5 plan, handoff |

---

## Prerequisites

- **n8n** 2.21.7+ running locally — default `http://localhost:5678`.
- **Python 3.10+** with `requests`.
- A **Telegram bot token** configured as an n8n *Telegram API* credential named `TelegramBot_MinTest` (the workflow references it by name).

## Setup

1. **Import the workflow**
   ```bash
   # UI: Settings → Workflows → Import → leadsentry_v4.json → Activate
   # or via the REST API:
   curl -X POST http://localhost:5678/api/v1/workflows \
        -H "X-N8N-API-KEY: $N8N_API_KEY" \
        -H "Content-Type: application/json" \
        -d @leadsentry_v4.json
   ```

2. **Set the webhook secret** (HMAC verification reads this at runtime). If unset, HMAC runs in pass-through mode.
   ```
   WEBHOOK_SECRET=<your-shared-secret>
   ```

3. **Create the Telegram credential** in n8n matching the name referenced in the workflow (`TelegramBot_MinTest`).

4. **Rebuild the workflow JSON** if you change `build_v4.py`:
   ```bash
   python build_v4.py      # writes leadsentry_v4.json next to the script
   ```

## Run the tests

Tests post payloads to the live webhook at `http://localhost:5678/webhook/leadsentry-v4`. Activate the workflow in n8n first.

```bash
python test_v4.py                   # main suite — 100 cases
python test_v4_comprehensive.py     # extended coverage
python test_v4_final.py             # post-deploy smoke
python stress_test_v4.py            # edge cases / load
python brutal_test.py               # brute-force fuzzing
```

---

## API

### `POST /webhook/leadsentry-v4`

Request:
```json
{
  "name": "Anita Sharma",
  "email": "anita@acme.io",
  "company": "Acme Corp",
  "phone": "+1 415 555 0182",
  "role": "VP Engineering",
  "budget": "$25k-$50k",
  "urgency": "high",
  "source": "referral",
  "description": "Looking to replace our internal lead-routing tool ASAP; we already use n8n."
}
```

Response (HTTP 200):
```json
{
  "status": "ok",
  "lead": { "name": "Anita Sharma", "email": "anita@acme.io", "company": "Acme Corp", "role": "VP Engineering" },
  "fitScore": 88,
  "intentScore": 78,
  "compositeScore": 83,
  "tier": "A",
  "category": "hot",
  "bant": { "budget": "$25k-$50k", "authority": "decision_maker", "need": "lead routing replacement", "timeline": "ASAP" },
  "routing": { "tier": "A", "category": "hot", "action": "immediate_outreach" },
  "next": "Send Calendly link within 1h",
  "notified": true
}
```

Rejections return HTTP **400** with a `{ "error": "...", "warnings": [...] }` payload for invalid input, or HTTP **400** with `{ "status": "rejected", "reason": "..." }` for spam.

---

## Security

- **No secrets in this repo.** `leadsentry_v4.json` contains only n8n credential *references* (ID + name); the Telegram token lives in n8n's encrypted credential store. HMAC verification reads `WEBHOOK_SECRET` from the environment at runtime.
- The n8n API key is **never committed** — tests that need it read it from your local n8n config / environment, not from a tracked file.
- `.gitignore` excludes `.env`, `_api_key.txt`, `*.key`, `*.pem`, and the local `n8n-config.json` (which references your n8n API key).
- Gate layers run in pass-through mode unless backed by Redis / a secret — see [Known limitations](#known-limitations) below.

A 27-issue engineering audit (covering `$json` access in "Run Once for All Items" mode, missing `onError` handlers, weak email/phone validation, Telegram-failure-drops-lead risk, and more) is preserved in [`AUDIT_REPORT.md`](AUDIT_REPORT.md) as a historical record. The v4 build reflects the fixes.

---

## Known limitations

These are pass-through placeholders in v4 and are addressed by the v5 plan:

1. **HMAC / rate limit / idempotency gates** need Redis to enforce (currently pass-through).
2. **No persistence** — leads vanish after the response is sent; needs PostgreSQL.
3. **Rule-based scoring only** — AI scoring via Ollama / Groq is planned for v5.
4. **No enrichment APIs** — Hunter.io / ZeroBounce / NumVerify integration is planned for v5.

## Roadmap

[`V5_UPGRADE_PLAN.md`](V5_UPGRADE_PLAN.md) sketches the next iteration: Ollama + Groq for BANT extraction, scoring, and competitor detection; enrichment APIs (Hunter.io, ZeroBounce, NumVerify); PostgreSQL for persistence; Redis-backed rate limiting and circuit breaking; HubSpot CRM; SendGrid outbound; and a WebSocket real-time dashboard. Target operating cost: $0 / month on free tiers.

---

## License

[MIT](LICENSE).