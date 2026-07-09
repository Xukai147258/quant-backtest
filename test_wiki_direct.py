import httpx, json
resp = httpx.get("https://en.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": "Python programming", "format": "json", "srlimit": 3}, timeout=10)
print("Status:", resp.status_code)
data = resp.json()
print("Keys:", list(data.keys()))
if "query" in data:
    print("Search results:", len(data["query"].get("search", [])))
    for item in data["query"]["search"][:2]:
        print("  -", item.get("title"))
else:
    print("No query key in response")
    print(json.dumps(data, indent=2)[:500])
