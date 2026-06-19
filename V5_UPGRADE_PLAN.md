# LeadSentry Pro v5 — Upgrade Plan

## Overview

Enterprise AI upgrade adding Ollama/Groq for intelligent lead analysis, enrichment APIs for data quality, PostgreSQL for persistence, Redis for caching, HubSpot CRM integration, and a real-time WebSocket dashboard.

**Target:** $0/month operating cost using free tiers  
**Status:** PLANNED — not yet implemented

---

## Free AI & API Stack

| Service | Free Limit | Purpose | n8n Method |
|---------|------------|---------|------------|
| **Ollama** | Unlimited (local) | BANT extraction, competitor detection, scoring | Native Ollama node |
| **Groq** | 14,400 RPD, 30 RPM | Fast cloud LLM fallback | HTTP Request (OpenAI-compatible) |
| **Google Gemini** | 500-1,500 RPD | Complex reasoning fallback | HTTP Request |
| **Hunter.io** | 50 email finds/month | B2B email finding | HTTP Request (REST API) |
| **ZeroBounce** | 100 verifications/month | Email validation | HTTP Request |
| **NumVerify** | 100 requests/month | Phone validation | HTTP Request |
| **SendGrid** | 100 emails/day | Email outreach | HTTP Request |
| **HubSpot** | Unlimited contacts | CRM integration | Native HubSpot node |
| **PostgreSQL** | Self-hosted | Data persistence | Native Postgres node |
| **Redis** | Self-hosted | Caching + rate limiting | Native Redis node |

---

## Phase 1: AI-Powered Lead Analysis

### Ollama Integration
```json
{
  "node": "Ollama Chat Model",
  "credentials": {
    "ollamaApi": {
      "baseURL": "http://host.docker.internal:11434"
    }
  },
  "model": "llama3.1:8b"
}
```

**Use cases:**
1. **BANT Extraction** — LLM parses description for budget, authority, need, timeline
2. **Competitor Detection** — Identify competitors mentioned in lead text
3. **Lead Scoring** — AI-powered quality assessment (replaces rule-based)
4. **Response Generation** — Personalized follow-up messages per lead

### Groq Fallback
```json
{
  "endpoint": "https://api.groq.com/openai/v1",
  "model": "llama-3.1-8b-instant",
  "apiKey": "${GROQ_API_KEY}"
}
```

**Limits:** 30 RPM, 6,000 TPM, 14,400 RPD (Llama 3.1 8B)

### AI Agent Node Architecture
```
Webhook → AI Agent (with tools) → Ollama/Groq → Score + BANT + Competitors
                                        ↓
                               HTTP Request Tool (enrichment)
                               Calculator Tool (scoring)
                               Code Tool (custom logic)
```

---

## Phase 2: Lead Enrichment & Validation

### Hunter.io (Email Finding)
```http
GET https://api.hunter.io/v2/email-finder?domain={company_domain}&first_name={first}&last_name={last}&api_key={key}
```
**Response:** `{ "data": { "email": "...", "confidence": 95, "position": "VP Engineering" } }`

### ZeroBounce (Email Validation)
```http
GET https://api.zerobounce.net/v2/validate?api_key={key}&email={email}
```
**Response:** `{ "status": "valid", "sub_status": "catch_all", "score": 0.95 }`

### NumVerify (Phone Validation)
```http
GET http://apilayer.net/api/validate?access_key={key}&number={phone}
```
**Response:** `{ "valid": true, "country_name": "United States", "carrier": "AT&T", "line_type": "mobile" }`

### Enrichment Pipeline
```
Receive Lead
  → Hunter.io (find email if not provided)
  → ZeroBounce (validate email)
  → NumVerify (validate phone)
  → Cache results in Redis (TTL 24h)
  → Proceed to scoring
```

---

## Phase 3: Data Persistence

### PostgreSQL Schema
```sql
-- Leads table
CREATE TABLE leads (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(255),
  name TEXT,
  company TEXT,
  role TEXT,
  phone TEXT,
  source VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  qualified_at TIMESTAMPTZ,
  status VARCHAR(20) DEFAULT 'new'
);

-- Lead scores
CREATE TABLE lead_scores (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(50) REFERENCES leads(lead_id),
  fit_score INTEGER,
  intent_score INTEGER,
  composite_score INTEGER,
  category VARCHAR(20),
  tier VARCHAR(5),
  scoring_model VARCHAR(20) DEFAULT 'v4',
  reasoning JSONB,
  scored_at TIMESTAMPTZ DEFAULT NOW()
);

-- BANT extraction
CREATE TABLE lead_bant (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(50) REFERENCES leads(lead_id),
  budget VARCHAR(100),
  authority VARCHAR(100),
  need TEXT,
  timeline VARCHAR(100),
  extracted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enrichment data
CREATE TABLE lead_enrichment (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(50) REFERENCES leads(lead_id),
  provider VARCHAR(50),
  data JSONB,
  enriched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interactions log
CREATE TABLE lead_interactions (
  id SERIAL PRIMARY KEY,
  lead_id VARCHAR(50) REFERENCES leads(lead_id),
  interaction_type VARCHAR(50),
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_created ON leads(created_at);
CREATE INDEX idx_scores_lead ON lead_scores(lead_id);
```

### n8n Postgres Node
```json
{
  "operation": "upsert",
  "table": "leads",
  "columns": "lead_id,email,name,company,role,phone,source,status",
  "matchingColumns": "lead_id"
}
```

---

## Phase 4: Redis Caching & Rate Limiting

### Caching Pattern
```
Redis GET cache:lead:{email}
  → HIT: use cached data
  → MISS: call enrichment API → Redis SET with TTL 86400
```

### Rate Limiting Pattern
```
Redis INCR rate:{ip}:{minute_bucket}
  → IF count > 100: reject (429)
  → ELSE: proceed
```

### Circuit Breaker State
```
Redis GET cb:{service}:state
  → OPEN: block calls (wait cooldown)
  → HALF-OPEN: allow 1 test call
  → CLOSED: normal operation
```

### n8n Redis Node
```json
{
  "operation": "get",
  "key": "cache:lead:{{ $json.email }}",
  "database": 0
}
```

---

## Phase 5: CRM Integration

### HubSpot (Free Tier)
```json
{
  "resource": "contact",
  "operation": "create",
  "email": "={{ $json.email }}",
  "firstName": "={{ $json.name.split(' ')[0] }}",
  "lastName": "={{ $json.name.split(' ').slice(1).join(' ') }}",
  "company": "={{ $json.company }}",
  "jobTitle": "={{ $json.role }}"
}
```

**Free tier:** Unlimited contacts, basic API (100 calls/10s)

### Lead-to-Deal Pipeline
```
IF compositeScore >= 70:
  HubSpot → Create Contact
  HubSpot → Create Deal (Stage: "Qualified Lead")
  HubSpot → Add Note (Score: {score}, BANT: {summary})

IF compositeScore 40-69:
  HubSpot → Create Contact
  HubSpot → Add Note (Nurture track)

IF compositeScore < 40:
  HubSpot → Create Contact (Stage: "Subscriber")
```

---

## Phase 6: Multi-Channel Outreach

### SendGrid (100 free emails/day)
```json
{
  "fromEmail": "leads@yourcompany.com",
  "toEmail": "={{ $json.recipient }}",
  "subject": "Re: Your inquiry — Score: {{ $json.score }}",
  "html": "<template>"
}
```

### Email Templates by Tier
| Tier | Template | Timing |
|------|----------|--------|
| Hot (A) | Immediate personal outreach | < 5 min |
| Warm (B) | Qualification email + calendar link | < 1 hour |
| Promising (B) | Case study + discovery call invite | < 4 hours |
| Nurture (C) | Welcome email + drip sequence | < 24 hours |
| Low Intent (C) | Re-engagement email | < 48 hours |
| Cold (D) | No outreach | N/A |

---

## Phase 7: Real-Time Dashboard

### WebSocket Node
```json
{
  "port": 8080,
  "path": "/ws/leads",
  "bindAddress": "0.0.0.0"
}
```

### Dashboard HTML (Single File)
- Live lead feed (WebSocket updates)
- Response time chart (last 24h)
- Score distribution histogram
- SLA compliance gauge
- Enrichment success rate
- Tier breakdown pie chart

### Dashboard Data Flow
```
Postgres (query metrics) → Code (format JSON) → WebSocket (broadcast)
                                                    ↓
                                              Dashboard HTML
```

---

## Implementation Priority

| Phase | Effort | Impact | Priority |
|-------|--------|--------|----------|
| 1. AI Analysis | Medium | HIGH — 40% better scoring | P0 |
| 2. Enrichment | Low | HIGH — 25% more data | P0 |
| 3. Persistence | Medium | HIGH — audit trail, analytics | P1 |
| 4. Redis | Low | MEDIUM — caching, rate limiting | P1 |
| 5. CRM | Medium | HIGH — sales team adoption | P1 |
| 6. Outreach | Low | MEDIUM — multi-channel | P2 |
| 7. Dashboard | Medium | MEDIUM — visibility | P2 |

---

## Estimated Impact

| Metric | v4 (Current) | v5 (Target) |
|--------|-------------|-------------|
| Scoring accuracy | Rule-based | +40% with AI |
| Data per lead | Basic fields | +25% with enrichment |
| Response time | 440ms | <500ms (cached) |
| Conversion | Baseline | +15% with personalization |
| Persistence | None | Full audit trail |
| CRM sync | None | Real-time HubSpot |
| Cost | $0/month | $0/month |

---

## Technical Notes

### n8n Version
- **Current:** 2.21.7 (downgraded from 2.23.4 due to IF node bug)
- **Bug:** IF node `typeVersion: 2` corrupts output data. Use `typeVersion: 2.2`.
- **Bug:** IF node connection target `index` must be `0` (Code nodes have one input).

### build_v4.py Wire Function
```python
def wire(src_name, tgt_name, idx=0, out="main", tgt_input=0):
    # idx = output index (IF branch: 0=TRUE, 1=FALSE)
    # tgt_input = target node input index (always 0 for Code/Respond nodes)
```

### Deployment
```python
# Strip read-only fields before PUT
allowed_keys = {'name', 'nodes', 'connections', 'settings', 'pinData'}
# Strip settings
allowed_settings = {'saveExecutionProgress', 'saveManualExecutions', 'callerPolicy', 'errorWorkflow'}
# Add Telegram credentials
"credentials": {"telegramApi": {"id": "9we9bC5LS0MRspOh", "name": "TelegramBot_MinTest"}}
```

---

## Files

| File | Purpose |
|------|---------|
| `V5_UPGRADE_PLAN.md` | This file |
| `ARCHITECTURE.md` | v4 architecture reference |
| `SESSION_HANDOFF.md` | Session handoff summary |
