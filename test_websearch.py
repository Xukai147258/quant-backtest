from duckduckgo_search import DDGS
ddgs = DDGS()
try:
    results = list(ddgs.text('Python async task scheduling framework', max_results=3))
    print(f"SUCCESS: got {len(results)} results")
    for r in results:
        print(f"- {r['title']}")
except Exception as e:
    print(f"DDGS failed: {e}")
    # Try with different backend
    try:
        results = list(ddgs.text("Python async task scheduling framework", max_results=3, backend="api"))
        print(f"API backend: got {len(results)} results")
    except Exception as e2:
        print(f"API backend also failed: {e2}")
