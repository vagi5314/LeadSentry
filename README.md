# LeadSentry Pro v4 — Enterprise Lead Qualifier

An enterprise-grade inbound lead qualification system built on [n8n](https://n8n.io).
Receives leads via webhook, applies multi-stage filtering, dual-axis scoring, BANT
extraction, routing, and Telegram notification — end-to-end in under 500ms.

| | |
|---|---|
| **Nodes** | 31 |
| **Connections** | 26 |
| **Test coverage** | 100/100 passing |
| **Avg response** | ~440–505 ms |
| **n8n version** | 2.21.7 (Docker) |
| **Webhook** | `POST /webhook/leadsentry-v4` |

---

## What it does

```
Receive → HMAC Verify → Rate Limit → Idempotency Gate → Bot/Spam Filter
  → Validate & Sanitize → Enrich → Score (dual-axis) → Route (BANT tiers)
  → Respond → Notify (Telegram)
```

Pipeline features: idempotency, HMAC webhook verification, rate limiting, bot/spam
detection, lead dedup, competitor detection, lead recycling, after-hours handling,
a dead-letter queue (DLQ), and SLA enforcement. A separate error-handler workflow
and an SLA monitor run alongside the main flow.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full node diagram, and
[`AUDIT_REPORT.md`](AUDIT_REPORT.md) for the security/robustness audit.

---

## Repository contents

| Path | Purpose |
|---|---|
| `build_v4.py` | Generates the n8n workflow JSON (`leadsentry_v4.json`). The source of truth for the workflow. |
| `leadsentry_v4.json` | Built workflow — import into n8n. |
| `test_v4.py` | Comprehensive test suite (HMAC, rate limit, idempotency, scoring, routing, edge cases…). |
| `test_v4_comprehensive.py` / `test_v4_final.py` | Extended + deployment verification tests. |
| `stress_test_v4.py` | Stress / edge-case harness against the live webhook. |
| `brutal_test.py` / `e2e_test_v3.py` | Brute-force and end-to-end test drivers. |
| `ARCHITECTURE.md` · `AUDIT_REPORT.md` · `V5_UPGRADE_PLAN.md` · `SESSION_HANDOFF.md` | Design + audit docs. |

> Scratch/debug scripts, old workflow snapshots, execution dumps, and screenshots
> are kept locally but excluded via `.gitignore`.

---

## Prerequisites

- **n8n** (2.21.7+) running locally — default `http://localhost:5678`.
- Python 3.10+ with `requests`.
- A Telegram bot token (configure as an n8n **Telegram API** credential named
  `TelegramBot_MinTest`; the workflow references it by name).

## Setup

1. **Import the workflow**
   ```bash
   # via n8n UI:  Import → leadsentry_v4.json → Activate
   # or via API (key from your n8n Settings → API):
   curl -X POST http://localhost:5678/api/v1/workflows \
        -H "X-N8N-API-KEY: $N8N_API_KEY" \
        -H "Content-Type: application/json" \
        -d @leadsentry_v4.json
   ```

2. **Set the webhook secret** (used by the HMAC verification node). In n8n,
   set an environment variable:
   ```
   WEBHOOK_SECRET=<your-shared-secret>
   ```
   If left unset, HMAC verification runs in pass-through mode.

3. **Create the Telegram credential** in n8n matching the name referenced in
   the workflow (`TelegramBot_MinTest`).

4. **Rebuild** the workflow JSON locally if you edit the builder:
   ```bash
   python build_v4.py      # writes leadsentry_v4.json next to the script
   ```

## Run the tests

Tests post payloads to the live webhook at `http://localhost:5678/webhook/leadsentry-v4`.
Make sure the workflow is **active** in n8n first.

```bash
python test_v4.py            # main suite (100 tests)
python test_v4_comprehensive.py
python stress_test_v4.py     # stress + edge cases
```

---

## Security notes

- **No secrets are stored in this repo.** Workflow JSON contains only n8n
  credential *references* (ID + name); actual Telegram/Notion tokens live in
  n8n's encrypted credential store. HMAC verification reads
  `WEBHOOK_SECRET` from the environment at runtime.
- The n8n API key is **never committed** — tests that need it read it from
  your local n8n config / environment, not from a tracked file.
- If you fork this: rotate any API keys, regenerate the Telegram bot token,
  and set a fresh `WEBHOOK_SECRET` before going live.

## License

Provided as-is for reference and reuse.
