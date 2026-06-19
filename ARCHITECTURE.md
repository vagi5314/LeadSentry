# LeadSentry Pro v4 — Architecture

## Overview

Enterprise-grade lead qualification system built on n8n. Receives inbound leads via webhook, applies multi-stage filtering, dual-axis scoring, BANT extraction, routing, and Telegram notification — all in under 500ms.

**Workflow ID:** `nDEzn3nxdAxebxgH`  
**Webhook:** `POST /webhook/leadsentry-v4`  
**n8n version:** 2.21.7 (Docker)  
**Nodes:** 31 | **Connections:** 26 | **Test coverage:** 100/100

---

## Architecture Diagram

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
                                                        TRUE ↓         ↓ FALSE
                                                     ┌──────────┐  ┌────────────────┐
                                                     │ Reject   │  │ Validate &     │
                                                     │ Spam     │  │ Sanitize       │
                                                     └────┬─────┘  │ (code)         │
                                                          │        └───────┬────────┘
                                                     ┌────▼─────┐         │
                                                     │ Respond  │  ┌──────▼──────┐
                                                     │ Spam 400 │  │  Is Valid?   │
                                                     └──────────┘  │  (IF node)  │
                                                                   └──┬───────┬──┘
                                                          TRUE ↓         ↓ FALSE
                                                     ┌──────────┐  ┌──────────────┐
                                                     │ Enrich   │  │ Format       │
                                                     │ Lead     │  │ Validation   │
                                                     │ (code)   │  │ Error (code) │
                                                     └────┬─────┘  └──────┬───────┘
                                                          │               │
                                                     ┌────▼─────┐  ┌─────▼──────┐
                                                     │ Score    │  │ Respond    │
                                                     │ Lead     │  │ 400        │
                                                     │ (code)   │  └────────────┘
                                                     └────┬─────┘
                                                          │
                                                     ┌────▼─────┐
                                                     │ Route    │
                                                     │ Lead     │
                                                     │ (code)   │
                                                     └────┬─────┘
                                                          │
                                                     ┌────▼─────┐
                                                     │ Build    │
                                                     │ Response │
                                                     │ (code)   │
                                                     └────┬─────┘
                                                          │
                                                     ┌────▼─────┐
                                                     │ Respond  │
                                                     │ Success  │
                                                     │ 200      │
                                                     └────┬─────┘
                                                          │
                                                     ┌────▼──────────┐
                                                     │ Needs         │
                                                     │ Notification? │
                                                     │ (IF node)     │
                                                     └──┬─────────┬──┘
                                                   TRUE ↓           ↓ FALSE
                                            ┌──────────────┐  ┌──────────┐
                                            │ Build TG     │  │ No       │
                                            │ Message      │  │ Notif.   │
                                            │ (code)       │  │ (noop)   │
                                            └──────┬───────┘  └──────────┘
                                                   │
                                            ┌──────▼───────┐
                                            │ Telegram:    │
                                            │ Alert        │
                                            │ (telegram)   │
                                            └──────────────┘
```

---

## Node Inventory

| Type | Count | Nodes |
|------|-------|-------|
| Code | 15 | HMAC Verify, Rate Limit Check, Idempotency Gate, Bot & Spam Filter, Validate & Sanitize, Enrich Lead, Score Lead, Route Lead, Build Response, Build TG Message, Log Error, Build DLQ Alert, Build SLA Alert, SLA Check |
| IF | 4 | Is Spam?, Is Valid?, Needs Notification?, Has SLA Breaches? |
| Respond to Webhook | 3 | Respond Spam 400, Respond 400, Respond Success |
| Telegram | 3 | Telegram: Alert, DLQ Telegram Alert, SLA Breach Alert |
| Webhook | 1 | Receive Lead |
| Error Trigger | 1 | Error Trigger |
| Schedule Trigger | 1 | SLA Monitor |
| NoOp | 2 | No Notification, No SLA Breach |

---

## Data Flow

### Stage 1: Gate Layer (Security)
| Node | Purpose | Failure Action |
|------|---------|----------------|
| Receive Lead | Webhook trigger, extracts body | Reject |
| HMAC Verify | Signature verification (placeholder) | Pass-through (no secret configured) |
| Rate Limit Check | Throttle abuse (placeholder) | Pass-through (no Redis) |
| Idempotency Gate | Dedup execution (placeholder) | Pass-through (no Redis) |

### Stage 2: Filter Layer (Bot/Spam)
| Node | Purpose | Failure Action |
|------|---------|----------------|
| Bot & Spam Filter | Disposable emails, honeypots, bot names, entropy | → Respond Spam 400 |
| Is Spam? | IF node routes spam vs legit | TRUE → Reject, FALSE → Validate |

### Stage 3: Validation Layer
| Node | Purpose | Failure Action |
|------|---------|----------------|
| Validate & Sanitize | Name min 2 chars, email format, budget/urgency/source normalization | → Format Validation Error → Respond 400 |
| Is Valid? | IF node routes valid vs invalid | TRUE → Enrich, FALSE → Respond 400 |

### Stage 4: Scoring Layer
| Node | Purpose |
|------|---------|
| Enrich Lead | Add enrichment data (email type, role level, company size) |
| Score Lead | Dual-axis scoring: Fit (0-100) + Intent (0-100) → Composite |
| Route Lead | 6-tier routing: hot(A), warm(B), promising(B), nurture(C), low_intent(C), cold(D) |
| Build Response | Assemble full response with score, BANT, routing, next action |

### Stage 5: Response Layer
| Node | Purpose |
|------|---------|
| Respond Success | HTTP 200 with full lead data |
| Needs Notification? | IF: compositeScore >= 40? |
| Build TG Message | Format Telegram alert with score, BANT, routing |
| Telegram: Alert | Send to chat ID 1794140046 |

### Stage 6: Error Handler
| Node | Purpose |
|------|---------|
| Error Trigger | Catches any node failure in workflow |
| Log Error | Structured error log (timestamp, executionId, failedNode, error) |
| Build DLQ Alert | Format error message for Telegram |
| DLQ Telegram Alert | Send error alert to same chat |

### Stage 7: SLA Monitor
| Node | Purpose |
|------|---------|
| SLA Monitor | Scheduled trigger (runs periodically) |
| SLA Check | Check for leads exceeding response time SLA |
| Build SLA Alert | Format SLA breach message |
| Has SLA Breaches? | IF: any breaches found? |
| SLA Breach Alert | Send breach notification to Telegram |
| No SLA Breach | No-op when no breaches |

---

## Scoring Model

### Fit Score (0-100)
| Component | Max Points | Logic |
|-----------|------------|-------|
| Email quality | 25 | Corporate > free provider |
| Company | 15 | Known company name |
| Role/Seniority | 25 | C-suite > VP > Director > Manager > IC |
| Company size | 20 | Enterprise > mid-market > small > startup |
| Contact completeness | 15 | Phone, LinkedIn, website present |

### Intent Score (0-100)
| Component | Max Points | Logic |
|-----------|------------|-------|
| Budget signal | 25 | Explicit budget amount, range keywords |
| Urgency | 20 | Critical > high > medium > low |
| Description quality | 20 | Pain points, competitor mentions, timeline |
| Pain signals | 15 | Frustration words, urgency phrases |
| Decision authority | 10 | "I decide", "approver", "budget owner" |
| Source quality | 10 | Referral > LinkedIn > website > cold |

### Composite Score
`compositeScore = (fitScore * 0.5) + (intentScore * 0.5)`

### Routing Tiers
| Tier | Category | Score Range | Action |
|------|----------|-------------|--------|
| A | hot | composite >= 70 AND intent >= 60 | Immediate outreach |
| B | warm | composite >= 60 OR intent >= 70 | Qualify & nurture |
| B | promising | composite >= 40 AND intent >= 60 | Discovery call |
| C | nurture | composite >= 40 OR intent >= 20 | Drip campaign |
| C | low_intent | composite >= 40 AND intent < 20 | Re-engage |
| D | cold | composite < 40 AND intent < 20 | Archive |

---

## BANT Extraction

| Component | Signals Extracted |
|-----------|-------------------|
| Budget | Explicit amounts, range keywords ($10K-$50K), "budget approved" |
| Authority | Role analysis (CEO=decision_maker, VP= influencer, Manager= user) |
| Need | Pain points, frustration words, "need", "require", "looking for" |
| Timeline | Urgency words ("ASAP", "this quarter", "Q2"), deadline mentions |

---

## Security Layers

1. **HMAC Verification** — Webhook signature validation (placeholder, needs secret)
2. **Rate Limiting** — Per-IP throttle (placeholder, needs Redis)
3. **Idempotency** — Duplicate execution prevention (placeholder, needs Redis)
4. **Bot Filter** — Disposable emails, honeypots, bot patterns, entropy analysis
5. **Input Sanitization** — XSS prevention, SQL injection blocking, length limits
6. **Email Validation** — Format check, domain validation, TLD check

---

## Error Handling

- **Error Trigger** catches any node failure in the workflow
- **DLQ (Dead Letter Queue)** sends Telegram alert with structured error data
- **SLA Monitor** periodically checks for response time breaches
- All errors include: timestamp, executionId, workflowId, failedNode, error message

---

## Performance

| Metric | Value |
|--------|-------|
| Avg response time | 440ms |
| Test coverage | 100/100 |
| Node count | 31 |
| Entry points | 3 (webhook, error trigger, schedule) |
| Leaf nodes | 7 (respond/telegram nodes) |

---

## Known Limitations (v4)

1. **HMAC/Rate Limit/Idempotency** — Gate nodes are pass-through placeholders. Need Redis for production.
2. **No data persistence** — Leads vanish after response. Need PostgreSQL.
3. **No CRM integration** — Results not pushed to HubSpot/Salesforce.
4. **No AI scoring** — Rule-based only. Ollama/Groq integration planned for v5.
5. **No enrichment APIs** — Hunter.io/ZeroBounce integration planned for v5.
6. **Layout** — Visual layout spread across canvas. Compact layout planned for v5.

---

## Files

| File | Purpose |
|------|---------|
| `leadsentry_v4.json` | Deployed workflow JSON |
| `build_v4.py` | Workflow builder script |
| `deploy_v4.py` | Deployment script |
| `test_v4_comprehensive.py` | 100-test E2E suite |
| `ARCHITECTURE.md` | This file |
| `V5_UPGRADE_PLAN.md` | Future upgrade plan |
| `SESSION_HANDOFF.md` | Session handoff summary |
