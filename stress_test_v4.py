"""
LeadSentry Pro v4 — Stress Test Suite
Tests: empty payload, edge cases, C-tier patterns, all routing tiers
"""
import requests, json, time, sys

BASE = "http://localhost:5678/webhook/leadsentry-v4"
PASS = 0; FAIL = 0; TOTAL = 0
results = []

def test(name, payload, expected_category=None, min_score=None):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    try:
        r = requests.post(BASE, json=payload, timeout=10)
        data = r.json()
        score = data.get('scoring', {})
        cat = score.get('category', 'N/A')
        comp = score.get('compositeScore', 0)
        tier = score.get('tier', 'N/A')
        status = data.get('status', 'N/A')

        ok = True
        notes = []
        if expected_category and cat != expected_category:
            ok = False
            notes.append(f"expected cat={expected_category} got={cat}")
        if min_score and comp < min_score:
            ok = False
            notes.append(f"expected score>={min_score} got={comp}")

        if ok:
            PASS += 1
            mark = "PASS"
        else:
            FAIL += 1
            mark = "FAIL"

        print(f"  [{mark}] {name}")
        print(f"         status={status} cat={cat} tier={tier} score={comp}/100")
        if notes:
            for n in notes:
                print(f"         -> {n}")
        results.append((name, mark, status, cat, tier, comp))
    except Exception as e:
        FAIL += 1
        TOTAL += 1
        print(f"  [FAIL] {name} — CRASH: {e}")

# ── 1. Edge Cases ──
print("\n=== 1. EDGE CASES ===")
test("Empty JSON", {}, expected_category=None)
test("Empty object", {"x": "y"}, expected_category=None)
test("Null fields", {"name": None, "email": None}, expected_category=None)
test("String 'null'", {"name": "null", "email": "null@test.com"}, expected_category='cold')
test("Minimal valid", {"name": "Test", "email": "test@company.com"}, expected_category='cold')

# ── 2. C-Tier Patterns ──
print("\n=== 2. C-TIER NURTURE PATTERNS ===")
test("Nurture: no role, no budget, no desc",
     {"name": "John Doe", "email": "john@gmail.com", "company": "Startup Inc"},
     expected_category='nurture', min_score=40)
test("Nurture: low intent, good fit",
     {"name": "Alice Smith", "email": "alice@bigcorp.com", "company": "BigCorp", "role": "Manager", "phone": "+1234567890", "description": "We have some problems with our current system."},
     expected_category=None)
test("Nurture: personal email, mid role",
     {"name": "Bob", "email": "bob@gmail.com", "company": "MidCo", "role": "Director", "phone": "+16505551234", "company_size": "500", "description": "We're evaluating new solutions for our team but no rush yet."},
     expected_category=None)

# ── 3. All Score Brackets ──
print("\n=== 3. SCORE BRACKETS ===")
# Hot A (fit>=70, intent>=70)
test("Hot A: CTO, enterprise, budget, urgent",
     {"name": "Jane Smith", "email": "jane@acmecorp.com", "company": "Acme Corp", "role": "CTO", "phone": "+14155551234", "company_size": "500", "budget": "150k", "urgency": "high", "description": "We are struggling with lead conversion and need a solution urgently. Our current system is too slow and we are losing revenue. We have a budget allocated for this quarter and need to implement immediately."},
     expected_category='hot', min_score=70)
# Hot A (fit>=70, intent>=60)
test("Hot A-: VP, enterprise, good budget",
     {"name": "Mark VP", "email": "mark@enterprise.com", "company": "Enterprise Inc", "role": "VP Engineering", "phone": "+14155559876", "company_size": "2000", "budget": "200k", "urgency": "high", "description": "We need to improve our lead conversion system. We have budget approved for Q3. Looking at solutions now. Please contact us soon."},
     expected_category='hot', min_score=60)
# Warm B (fit>=70, intent>=30)
test("Warm B: senior, low urgency",
     {"name": "Senior Dev", "email": "dev@bigtech.com", "company": "BigTech", "role": "Senior Engineer", "phone": "+14155553333", "company_size": "1000", "urgency": "low", "description": "Just browsing what solutions exist for lead management."},
     expected_category='warm', min_score=30)
# Promising B (fit>=40, intent>=60)
test("Promising B: lower role, high intent",
     {"name": "Coordinator", "email": "coord@midcorp.com", "company": "MidCorp", "role": "Coordinator", "phone": "+14155554444", "company_size": "100", "budget": "80k", "urgency": "high", "description": "We urgently need a new system. Our current one is broken and we are losing money every day. Looking to buy immediately."},
     expected_category='promising', min_score=40)
# Low intent C (fit>=70, intent<30)
test("Low Intent C: good fit, zero intent",
     {"name": "Well Fit", "email": "fit@enterprise.com", "company": "Enterprise Inc", "role": "CEO", "phone": "+14155555555", "company_size": "5000", "description": "Hello"},
     expected_category='low_intent', min_score=None)
# Nurture C (fit>=40, intent>=20)
test("Nurture C: mid fit, mid intent",
     {"name": "Nurture Me", "email": "nurture@midco.com", "company": "MidCo", "role": "Manager", "phone": "+14155556666", "company_size": "50", "urgency": "medium", "description": "We might be interested in learning more about your platform."},
     expected_category='nurture', min_score=20)
# Cold D (fit<40)
test("Cold D: poor fit",
     {"name": "Cold Lead", "email": "cold@gmail.com", "description": "hi"},
     expected_category='cold', min_score=None)

# ── 4. Spam / Bot ──
print("\n=== 4. SPAM & BOT ===")
test("Disposable email", {"name": "Spammy", "email": "spam@mailinator.com"})
test("Bot UA", {"name": "Botty", "email": "bot@test.com", "email": "bot@real.com", "user_agent": "curl/7.68.0"})
test("Test pattern email", {"name": "Test", "email": "test@test.com"})
test("Honeypot filled", {"name": "Real", "email": "real@company.com", "website_url": "http://spam.com"})
test("Garbage desc", {"name": "Garbage", "email": "garbage@test.com", "description": "aaaaa aaaa aaaa aaaa aaaaa"})

# ── 5. C-Tier Deep Dive ──
print("\n=== 5. C-TIER DEEP DIVE ===")
# Why are things C-tier? Let's test boundary conditions
test("Low budget, no role, personal email",
     {"name": "Test User", "email": "user@gmail.com", "company": "SmallBiz", "description": "We need help with our sales."})
test("No phone, no role, small company",
     {"name": "Another User", "email": "another@yahoo.com", "company": "TinyCo", "company_size": "5", "description": "Looking for a solution."})
test("Bare minimum hot candidate",
     {"name": "Best Lead", "email": "best@corporation.com", "company": "Corporation Inc", "role": "CTO", "phone": "+14155550000", "company_size": "1000", "budget": "100k", "urgency": "urgent", "description": "We are having major problems with our current pipeline. Our team is frustrated and we need to find a replacement immediately. This is costing us money every month and our VP is demanding a solution this quarter. Please contact us ASAP with pricing and demo options."})

# ── 6. Performance ──
print("\n=== 6. PERFORMANCE (10 rapid requests) ===")
times = []
for i in range(10):
    payload = {"name": f"Perf {i}", "email": f"perf{i}@testcorp.com", "company": "TestCorp", "role": "Engineer", "description": "Testing system performance under load."}
    start = time.time()
    try:
        r = requests.post(BASE, json=payload, timeout=10)
        r.json()
        times.append((time.time() - start) * 1000)
    except:
        pass
    time.sleep(0.3)

if times:
    print(f"  Avg: {sum(times)/len(times):.0f}ms  Min: {min(times):.0f}ms  Max: {max(times):.0f}ms")

# ── Summary ──
print(f"\n{'='*60}")
print(f"RESULTS: {PASS} PASS / {FAIL} FAIL / {TOTAL} TOTAL")
print(f"{'='*60}")

# Category distribution
cats = {}
for n, m, s, cat, tier, score in results:
    if m == "PASS":
        cats[cat or 'N/A'] = cats.get(cat or 'N/A', 0) + 1
print(f"\nCategory distribution (passing):")
for c, count in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {count}")
