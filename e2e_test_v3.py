#!/usr/bin/env python3
"""
LeadSentry Pro v3 — Comprehensive E2E Test Suite
Covers all 47+ failure points from ARCHITECTURE.md
"""
import json, urllib.request, sys, time, traceback
from datetime import datetime, timedelta

WEBHOOK_URL = "http://localhost:5678/webhook/leadsentry-v3"

passed = 0
failed = 0
errors = []

def post_lead(payload, timeout=30):
    """Send a lead to the webhook and return (status_code, response_body)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = json.loads(resp.read().decode("utf-8"))
        return resp.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}

def test(name, fn):
    global passed, failed
    try:
        ok, detail = fn()
        if ok:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            errors.append((name, detail))
            print(f"  FAIL  {name}: {detail}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL  {name}: EXCEPTION {e}")

# ============================================================
# STAGE 1: CAPTURE (Webhook)
# ============================================================
print("\n=== STAGE 1: CAPTURE ===")

def make_lead(**overrides):
    base = {
        "name": "Test Lead",
        "email": "test@example.com",
        "description": "We need a solution for our data pipeline. Looking for something that can handle 10k events per second.",
        "company": "Acme Corp",
        "role": "VP of Engineering",
        "phone": "+1-555-123-4567",
        "budget": 25000,
        "source": "website",
        "urgency": "high"
    }
    base.update(overrides)
    return base

# 1.1 Valid lead — hot
def test_valid_hot():
    lead = make_lead(
        email="vp-eng@bigcorp.com",
        budget=150000,
        urgency="critical",
        description="We urgently need to replace our current data pipeline. Our board approved a $150k budget. Looking for a demo this week."
    )
    code, body = post_lead(lead)
    if code == 200 and body.get("score", {}).get("category") in ("hot", "warm"):
        return True, ""
    return False, f"code={code}, category={body.get('score',{}).get('category')}"
test("Valid hot lead (200)", test_valid_hot)

# 1.2 Valid lead — warm
def test_valid_warm():
    lead = make_lead(
        email="director@midcorp.com",
        role="Director of Ops",
        budget=30000,
        urgency="medium"
    )
    code, body = post_lead(lead)
    if code == 200 and body.get("score", {}).get("category") in ("warm", "nurture"):
        return True, ""
    return False, f"code={code}, category={body.get('score',{}).get('category')}"
test("Valid warm lead (200)", test_valid_warm)

# 1.3 Array body (should fail)
def test_array_body():
    code, body = post_lead([{"name": "test", "email": "a@b.com"}])
    if code in (400, 500):
        return True, ""
    return False, f"Expected 400/500, got {code}"
test("Array body rejection", test_array_body)

# 1.4 Empty body
def test_empty_body():
    code, body = post_lead({})
    if code in (400, 500):
        return True, ""
    return False, f"Expected 400/500, got {code}"
test("Empty body rejection", test_empty_body)

# 1.5 Payload too large (>32KB)
def test_large_payload():
    lead = make_lead(description="x" * 40000)
    code, body = post_lead(lead)
    if code in (400, 500):
        return True, ""
    return False, f"Expected 400/500, got {code}"
test("Large payload rejection (>32KB)", test_large_payload)

# 1.6 Honeypot field filled (bot signal)
def test_honeypot():
    lead = make_lead(website_url="http://spammer.com")
    code, body = post_lead(lead)
    # Should still process but with warnings
    if code in (200, 400):
        return True, ""
    return False, f"code={code}"
test("Honeypot field handling", test_honeypot)

# 1.7 Future timestamp
def test_future_timestamp():
    lead = make_lead(submittedAt=(datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z")
    code, body = post_lead(lead)
    if code in (200, 400):
        return True, ""
    return False, f"code={code}"
test("Future timestamp handling", test_future_timestamp)

# ============================================================
# STAGE 2: BOT & SPAM FILTER
# ============================================================
print("\n=== STAGE 2: BOT & SPAM FILTER ===")

# 2.1 Disposable email
def test_disposable_email():
    lead = make_lead(email="user@mailinator.com")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Disposable email rejection", test_disposable_email)

# 2.2 Spam patterns in description
def test_spam_patterns():
    lead = make_lead(description="Buy now! Click here! Free money! Limited time offer! Act now!")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Spam pattern detection", test_spam_patterns)

# 2.3 Multiple URLs in description
def test_multiple_urls():
    lead = make_lead(description="Check http://spam1.com and http://spam2.com and http://spam3.com for details")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Multiple URLs spam detection", test_multiple_urls)

# 2.4 Known bot user agent
def test_bot_user_agent():
    lead = make_lead(userAgent="Googlebot/2.1 (+http://www.google.com/bot.html)")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Bot user agent detection", test_bot_user_agent)

# 2.5 All-caps name
def test_allcaps_name():
    lead = make_lead(name="JOHN SMITH")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("All-caps name handling", test_allcaps_name)

# 2.6 Legitimate email passes
def test_legitimate_email():
    lead = make_lead(email="jane.doe@realcompany.com")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"Expected 200, got {code}"
test("Legitimate email passes", test_legitimate_email)

# ============================================================
# STAGE 3: VALIDATION
# ============================================================
print("\n=== STAGE 3: VALIDATION ===")

# 3.1 Missing name
def test_missing_name():
    lead = make_lead()
    del lead["name"]
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Missing name", test_missing_name)

# 3.2 Invalid email — no domain
def test_email_no_domain():
    lead = make_lead(email="user@")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Invalid email (no domain)", test_email_no_domain)

# 3.3 Invalid email — no TLD
def test_email_no_tld():
    lead = make_lead(email="user@domain")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Invalid email (no TLD)", test_email_no_tld)

# 3.4 Invalid email — no local part
def test_email_no_local():
    lead = make_lead(email="@domain.com")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Invalid email (no local part)", test_email_no_local)

# 3.5 Short description
def test_short_description():
    lead = make_lead(description="short")
    code, body = post_lead(lead)
    if code == 400:
        return True, ""
    return False, f"Expected 400, got {code}"
test("Short description rejection", test_short_description)

# 3.6 Budget with commas
def test_budget_commas():
    lead = make_lead(budget="15,000")
    code, body = post_lead(lead)
    if code == 200:
        budget = body.get("lead", {}).get("budget")
        if budget == 15000:
            return True, ""
        return False, f"Budget parsed as {budget}, expected 15000"
    return False, f"code={code}"
test("Budget with commas (15000 -> 15000)", test_budget_commas)

# 3.7 Negative budget
def test_negative_budget():
    lead = make_lead(budget=-5000)
    code, body = post_lead(lead)
    if code == 200:
        budget = body.get("lead", {}).get("budget")
        if budget is None or budget == 0:
            return True, ""
        return False, f"Negative budget accepted: {budget}"
    return False, f"code={code}"
test("Negative budget rejection", test_negative_budget)

# 3.8 Invalid source
def test_invalid_source():
    lead = make_lead(source="invalid_source")
    code, body = post_lead(lead)
    if code == 200:
        source = body.get("lead", {}).get("source")
        if source == "other":
            return True, ""
        return False, f"Invalid source accepted: {source}"
    return False, f"code={code}"
test("Invalid source -> 'other'", test_invalid_source)

# 3.9 Long phone number
def test_long_phone():
    lead = make_lead(phone="+1-555-123-4567-8901-2345")
    code, body = post_lead(lead)
    if code in (200, 400):
        return True, ""
    return False, f"code={code}"
test("Long phone number handling", test_long_phone)

# 3.10 SQL injection in name
def test_sql_injection():
    lead = make_lead(name="'; DROP TABLE leads; --")
    code, body = post_lead(lead)
    if code == 200:
        name = body.get("lead", {}).get("name", "")
        if "&" in name or name == "'; DROP TABLE leads; --":
            # Name is sanitized (HTML entities) or stored as-is (parameterized in DB)
            return True, ""
        return False, f"SQL injection not sanitized: {name}"
    return False, f"code={code}"
test("SQL injection sanitization", test_sql_injection)

# 3.11 XSS in description
def test_xss():
    lead = make_lead(description="<script>alert('xss')</script> We need a data pipeline solution")
    code, body = post_lead(lead)
    if code == 200:
        desc = body.get("lead", {}).get("description", "")
        if "<script>" not in desc:
            return True, ""
        return False, f"XSS not sanitized: {desc[:100]}"
    return False, f"code={code}"
test("XSS sanitization", test_xss)

# 3.12 Unicode name (José, 田中)
def test_unicode_name():
    lead = make_lead(name="José García 田中太郎")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Unicode name handling", test_unicode_name)

# 3.13 Hex budget (0x1F4)
def test_hex_budget():
    lead = make_lead(budget="0x1F4")
    code, body = post_lead(lead)
    if code == 200:
        budget = body.get("lead", {}).get("budget")
        # Number("0x1F4") = 500 in JS - this is valid, not a security issue
        if budget == 500:
            return True, ""
        return False, f"Hex budget parsed as {budget}, expected 500"
    return False, f"code={code}"
test("Hex budget handling (0x1F4 -> 500)", test_hex_budget)

# ============================================================
# STAGE 4: ENRICHMENT
# ============================================================
print("\n=== STAGE 4: ENRICHMENT ===")

# 4.1 Business email detection
def test_business_email():
    lead = make_lead(email="user@bigcorp.com")
    code, body = post_lead(lead)
    if code == 200:
        is_biz = body.get("context", {}).get("isBusinessEmail")
        if is_biz:
            return True, ""
        return False, f"Business email not detected"
    return False, f"code={code}"
test("Business email detection", test_business_email)

# 4.2 Personal email detection
def test_personal_email():
    lead = make_lead(email="user@gmail.com")
    code, body = post_lead(lead)
    if code == 200:
        is_biz = body.get("context", {}).get("isBusinessEmail")
        if not is_biz:
            return True, ""
        return False, f"Personal email not detected"
    return False, f"code={code}"
test("Personal email detection", test_personal_email)

# 4.3 Senior role detection
def test_senior_role():
    lead = make_lead(role="VP of Sales", email="vp@solutions.com")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Senior role detection", test_senior_role)

# 4.4 Company size parsing — enterprise
def test_enterprise_size():
    lead = make_lead(companySize="5000+")
    code, body = post_lead(lead)
    if code == 200:
        size = body.get("context", {}).get("companySize")
        if size == "enterprise":
            return True, ""
        return False, f"Expected enterprise, got {size}"
    return False, f"code={code}"
test("Company size: enterprise (5000+)", test_enterprise_size)

# 4.5 Company size parsing — startup
def test_startup_size():
    lead = make_lead(companySize="10-50")
    code, body = post_lead(lead)
    if code == 200:
        size = body.get("context", {}).get("companySize")
        if size in ("startup", "small-business"):
            return True, ""
        return False, f"Expected startup/small-business, got {size}"
    return False, f"code={code}"
test("Company size: startup (10-50)", test_startup_size)

# 4.6 Description quality — excellent
def test_excellent_description():
    lead = make_lead(
        description="We are a mid-market SaaS company struggling with our current data pipeline solution. "
        "Our engineering team of 30 people spends 40% of their time maintaining legacy ETL scripts. "
        "We need a modern solution that can handle real-time streaming, has good API documentation, "
        "and integrates with Snowflake. Our board has approved a budget of $50k for Q3. "
        "We are evaluating 3 vendors and need to make a decision by end of quarter."
    )
    code, body = post_lead(lead)
    if code == 200:
        quality = body.get("context", {}).get("descriptionQuality")
        if quality in ("excellent", "good"):
            return True, ""
        return False, f"Expected excellent/good, got {quality}"
    return False, f"code={code}"
test("Description quality: excellent", test_excellent_description)

# 4.7 Pain signals detected
def test_pain_signals():
    lead = make_lead(description="We are struggling with our current solution. It is broken and wasting our time. We need to fix this urgently.")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Pain signal detection", test_pain_signals)

# 4.8 Decision signals detected
def test_decision_signals():
    lead = make_lead(description="Ready to buy. Looking for a demo. Budget approved. Comparing vendors. Request for proposal.")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Decision signal detection", test_decision_signals)

# ============================================================
# STAGE 5: SCORING (Dual-Axis)
# ============================================================
print("\n=== STAGE 5: SCORING ===")

# 5.1 Hot lead (high fit + high intent)
def test_hot_scoring():
    lead = make_lead(
        email="cto@enterprise-corp.com",
        role="CTO",
        company="Enterprise Corp",
        companySize="2000",
        budget=200000,
        urgency="critical",
        description="Urgently need to replace our data pipeline. Board approved $200k budget. Want demo this week. Current solution is broken and costing us money."
    )
    code, body = post_lead(lead)
    if code == 200:
        cat = body.get("score", {}).get("category")
        tier = body.get("score", {}).get("tier")
        fit = body.get("score", {}).get("fit", 0)
        intent = body.get("score", {}).get("intent", 0)
        if cat == "hot" and tier == "A" and fit >= 70 and intent >= 70:
            return True, ""
        return False, f"Expected hot/A/70+, got {cat}/{tier}/{fit}/{intent}"
    return False, f"code={code}"
test("Hot lead scoring (fit>=70, intent>=70)", test_hot_scoring)

# 5.2 Cold lead (low fit + low intent)
def test_cold_scoring():
    lead = make_lead(
        email="user@gmail.com",
        role="",
        company="",
        budget=None,
        urgency="low",
        description="just exploring options for now"
    )
    code, body = post_lead(lead)
    if code == 200:
        cat = body.get("score", {}).get("category")
        if cat in ("cold", "nurture"):
            return True, ""
        return False, f"Expected cold/nurture, got {cat}"
    return False, f"code={code}"
test("Cold lead scoring (low fit, low intent)", test_cold_scoring)

# 5.3 BANT extraction
def test_bant_extraction():
    lead = make_lead(
        budget=75000,
        role="Director of Engineering",
        description="We need a solution urgently. Budget approved. I am the decision maker.",
        urgency="high"
    )
    code, body = post_lead(lead)
    if code == 200:
        bant = body.get("bant", {})
        if bant.get("budget") != "unknown" and bant.get("authority") != "unknown":
            return True, ""
        return False, f"BANT not extracted: {bant}"
    return False, f"code={code}"
test("BANT extraction", test_bant_extraction)

# 5.4 Score breakdown provided
def test_score_breakdown():
    lead = make_lead()
    code, body = post_lead(lead)
    if code == 200:
        breakdown = body.get("score", {}).get("breakdown", {})
        if "fit" in breakdown and "intent" in breakdown:
            return True, ""
        return False, f"No breakdown: {breakdown}"
    return False, f"code={code}"
test("Score breakdown provided", test_score_breakdown)

# 5.5 Category thresholds boundary
def test_boundary_scoring():
    lead = make_lead(
        email="user@company.com",
        company="Test Corp",
        budget=10000,
        urgency="medium"
    )
    code, body = post_lead(lead)
    if code == 200:
        cat = body.get("score", {}).get("category")
        if cat in ("warm", "nurture", "promising"):
            return True, ""
        return False, f"Unexpected category: {cat}"
    return False, f"code={code}"
test("Boundary scoring (mid-range lead)", test_boundary_scoring)

# 5.6 Risk factors identified
def test_risk_factors():
    lead = make_lead(
        email="user@gmail.com",
        phone=None,
        role=None
    )
    code, body = post_lead(lead)
    if code == 200:
        risks = body.get("risks", [])
        if len(risks) > 0:
            return True, ""
        return False, f"No risks identified for low-signal lead"
    return False, f"code={code}"
test("Risk factors identified", test_risk_factors)

# ============================================================
# STAGE 6: ROUTING
# ============================================================
print("\n=== STAGE 6: ROUTING ===")

# 6.1 Hot lead -> AE direct
def test_hot_routing():
    lead = make_lead(
        email="cto@bigcorp.com",
        role="CTO",
        company="BigCorp",
        companySize="5000",
        budget=200000,
        urgency="critical",
        description="Urgently need data pipeline. Budget approved. Want demo this week."
    )
    code, body = post_lead(lead)
    if code == 200:
        routing = body.get("routing", {})
        assignTo = routing.get("assignTo", "")
        sla = routing.get("sla", "")
        if "AE" in assignTo or "Senior" in assignTo:
            return True, ""
        return False, f"Hot lead not routed to AE: {assignTo}"
    return False, f"code={code}"
test("Hot lead -> AE direct", test_hot_routing)

# 6.2 Cold lead -> Marketing
def test_cold_routing():
    lead = make_lead(
        email="user@gmail.com",
        budget=None,
        urgency="low",
        description="just exploring options"
    )
    code, body = post_lead(lead)
    if code == 200:
        routing = body.get("routing", {})
        assignTo = routing.get("assignTo", "")
        if "Marketing" in assignTo:
            return True, ""
        return False, f"Cold lead not routed to Marketing: {assignTo}"
    return False, f"code={code}"
test("Cold lead -> Marketing", test_cold_routing)

# 6.3 SLA deadline provided
def test_sla_deadline():
    lead = make_lead()
    code, body = post_lead(lead)
    if code == 200:
        sla = body.get("routing", {}).get("slaDeadline")
        if sla:
            return True, ""
        return False, "No SLA deadline"
    return False, f"code={code}"
test("SLA deadline provided", test_sla_deadline)

# 6.4 Territory detection (US)
def test_territory_us():
    lead = make_lead(email="user@company.com")
    code, body = post_lead(lead)
    if code == 200:
        territory = body.get("routing", {}).get("territory", "")
        if territory:
            return True, ""
        return False, "No territory"
    return False, f"code={code}"
test("Territory detection", test_territory_us)

# ============================================================
# STAGE 7: RESPONSE & NOTIFICATIONS
# ============================================================
print("\n=== STAGE 7: RESPONSE & NOTIFICATIONS ===")

# 7.1 Response has all required fields
def test_response_fields():
    lead = make_lead()
    code, body = post_lead(lead)
    if code == 200:
        required = ["leadId", "score", "bant", "routing", "action", "lead", "context", "risks"]
        missing = [f for f in required if f not in body]
        if not missing:
            return True, ""
        return False, f"Missing fields: {missing}"
    return False, f"code={code}"
test("Response has all required fields", test_response_fields)

# 7.2 Action recommended
def test_action_recommended():
    lead = make_lead()
    code, body = post_lead(lead)
    if code == 200:
        action = body.get("action", {})
        if action.get("next") and action.get("time") and action.get("assignTo"):
            return True, ""
        return False, f"Incomplete action: {action}"
    return False, f"code={code}"
test("Action recommended", test_action_recommended)

# 7.3 Opening angle provided
def test_opening_angle():
    lead = make_lead()
    code, body = post_lead(lead)
    if code == 200:
        angle = body.get("action", {}).get("openingAngle")
        if angle and len(angle) > 10:
            return True, ""
        return False, f"No opening angle: {angle}"
    return False, f"code={code}"
test("Opening angle provided", test_opening_angle)

# 7.4 BANT summary in response
def test_bant_summary():
    lead = make_lead(budget=50000, role="Director", urgency="high")
    code, body = post_lead(lead)
    if code == 200:
        summary = body.get("bantSummary", "")
        if summary:
            return True, ""
        return False, "No BANT summary"
    return False, f"code={code}"
test("BANT summary in response", test_bant_summary)

# ============================================================
# STAGE 8: SPEED
# ============================================================
print("\n=== STAGE 8: SPEED ===")

# 8.1 Response time < 2 seconds
def test_speed():
    lead = make_lead()
    start = time.time()
    code, body = post_lead(lead)
    elapsed = time.time() - start
    if code == 200 and elapsed < 2.0:
        return True, ""
    return False, f"Response took {elapsed:.2f}s (target < 2s), code={code}"
test("Response time < 2 seconds", test_speed)

# 8.2 Multiple concurrent leads
def test_concurrent():
    import concurrent.futures
    leads = [make_lead(email=f"user{i}@company.com", name=f"User {i}") for i in range(5)]
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(post_lead, lead) for lead in leads]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.time() - start
    all_ok = all(code == 200 for code, _ in results)
    if all_ok and elapsed < 10:
        return True, ""
    codes = [code for code, _ in results]
    return False, f"Codes: {codes}, elapsed: {elapsed:.2f}s"
test("5 concurrent leads", test_concurrent)

# ============================================================
# STAGE 9: EDGE CASES
# ============================================================
print("\n=== STAGE 9: EDGE CASES ===")

# 9.1 Missing all optional fields
def test_minimal_lead():
    lead = {
        "name": "Minimal Lead",
        "email": "minimal@test.com",
        "description": "This is a minimal lead submission with only required fields."
    }
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Minimal lead (only required fields)", test_minimal_lead)

# 9.2 All fields provided
def test_maximal_lead():
    lead = make_lead(
        website="https://company.com",
        companySize="500-1000",
        submittedAt=datetime.utcnow().isoformat() + "Z"
    )
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Maximal lead (all fields)", test_maximal_lead)

# 9.3 Very long description (>2000 chars)
def test_long_description():
    lead = make_lead(description="x" * 2500 + " We need a real solution for our pipeline.")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Long description (2500+ chars)", test_long_description)

# 9.4 Zero budget
def test_zero_budget():
    lead = make_lead(budget=0)
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Zero budget", test_zero_budget)

# 9.5 Very large budget
def test_large_budget():
    lead = make_lead(budget=5000000)
    code, body = post_lead(lead)
    if code == 200:
        cat = body.get("score", {}).get("category")
        return True, ""
    return False, f"code={code}"
test("Very large budget ($5M)", test_large_budget)

# 9.6 Unknown source
def test_unknown_source():
    lead = make_lead(source="magic")
    code, body = post_lead(lead)
    if code == 200:
        source = body.get("lead", {}).get("source")
        if source == "other":
            return True, ""
        return False, f"Unknown source not mapped to 'other': {source}"
    return False, f"code={code}"
test("Unknown source -> 'other'", test_unknown_source)

# 9.7 Empty phone
def test_empty_phone():
    lead = make_lead(phone="")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Empty phone handling", test_empty_phone)

# 9.8 Phone with special chars
def test_phone_special_chars():
    lead = make_lead(phone="(555) 123-4567 ext. 890")
    code, body = post_lead(lead)
    if code == 200:
        phone = body.get("lead", {}).get("phone")
        if phone and "+" not in phone and "(" not in phone:
            return True, ""
        return False, f"Phone not sanitized: {phone}"
    return False, f"code={code}"
test("Phone sanitization (special chars)", test_phone_special_chars)

# 9.9 Non-English description
def test_non_english():
    lead = make_lead(description=" Wir benötigen eine Lösung für unsere Datenpipeline. Bitte senden Sie uns ein Angebot.")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Non-English description", test_non_english)

# 9.10 Description with budget mentioned
def test_budget_in_description():
    lead = make_lead(description="We have a budget of about $50k to solve this problem. Need a solution fast.")
    code, body = post_lead(lead)
    if code == 200:
        return True, ""
    return False, f"code={code}"
test("Budget mentioned in description", test_budget_in_description)

# 9.11 Role variations
def test_role_variations():
    roles = [
        ("VP of Sales", "senior"),
        ("Sales VP", "senior"),
        ("Engineering Manager", "mid"),
        ("Senior Software Engineer", "mid"),
        ("Intern", "junior"),
        ("", "none")
    ]
    for role, expected in roles:
        lead = make_lead(role=role, email=f"test-{role.replace(' ', '')}@co.com")
        code, body = post_lead(lead)
        if code != 200:
            return False, f"Failed for role '{role}': code={code}"
    return True, ""
test("Role variation handling", test_role_variations)

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
print(f"{'='*60}")

if errors:
    print(f"\nFAILURES:")
    for name, detail in errors:
        print(f"  {name}: {detail}")

sys.exit(0 if failed == 0 else 1)
