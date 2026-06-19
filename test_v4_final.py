import requests, json, urllib.request, time

# Test legitimate lead on v4
r = requests.post('http://localhost:5678/webhook/leadsentry-v4', json={
    'name': 'Test User', 'email': 'john@acme.com', 'phone': '+1234567890',
    'company': 'Acme Corp', 'role': 'VP Engineering', 'company_size': '500',
    'budget': 50000, 'urgency': 'high', 'source': 'website',
    'description': 'Need help with data pipeline migration. Budget approved this quarter.'
}, headers={'Content-Type': 'application/json'}, timeout=10)
body = r.text.encode('ascii', 'replace').decode('ascii')
print(f'Legitimate: {r.status_code} Body: {body[:600]}')

time.sleep(2)

# Check execution
c = json.load(open(r'C:\Users\ELCOT\.claude\n8n-config.json'))
req = urllib.request.Request('http://localhost:5678/api/v1/executions?limit=1&includeData=true', headers={'X-N8N-API-KEY': c['api_key']})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
for ex in data.get('data', []):
    rd = ex.get('data', {}).get('resultData', {})
    print(f'\nExecution {ex["id"]}: status={ex["status"]}')
    print(f'  Last node: {rd.get("lastNodeExecuted")}')
    err = rd.get('error')
    if err:
        print(f'  Error: {err.get("message", "?")[:200]}')
    run_data = rd.get('runData', {})
    for node_name, runs in run_data.items():
        if runs:
            last = runs[-1]
            status = last.get('executionStatus', '?')
            branches = last.get('data', {}).get('main', [])
            counts = [len(b) for b in branches]
            print(f'  {node_name}: {status} outputs={counts}')
            for bi, branch in enumerate(branches):
                if branch:
                    j = branch[0].get('json', {})
                    if 'status' in j: print(f'    branch {bi}: status={j["status"]}')
                    if 'scoring' in j: print(f'    branch {bi}: category={j["scoring"].get("category")}')
                    if 'response' in j:
                        resp_data = j['response']
                        print(f'    branch {bi}: response.status={resp_data.get("status")} score={resp_data.get("qualification",{}).get("score")}')
