import httpx, json, time, sys

def wait_for_server(base_url):
    print("Waiting for server...")
    for _ in range(30):
        try:
            r = httpx.get(f"{base_url}/health", timeout=5.0)
            if r.status_code == 200:
                print("Server up!")
                return True
        except Exception:
            time.sleep(1)
    return False

def execute():
    base_url = "http://127.0.0.1:8000"
    if not wait_for_server(base_url):
        sys.exit(1)

    with open("test_brand_nova.txt", "rb") as f:
        httpx.post(f"{base_url}/onboard-brand", files={"file": ("test_brand_nova.txt", f, "text/plain")}, timeout=30.0)

    payload = {
      "feature_name": "AI Campaign Autopilot",
      "description": "A new NovaTech AI feature that automatically drafts, scores, and publishes multi-channel marketing campaigns from a single product brief — with zero manual formatting needed.",
      "target_audience": "Enterprise marketing directors and CMOs at B2B tech companies",
      "tone": "bold and strategic",
      "platforms": ["linkedin", "twitter", "instagram"],
      "brand_name": "NovaTech AI"
    }
    
    print("Generating...")
    r = httpx.post(f"{base_url}/generate-sync", json=payload, timeout=120.0)
    data = r.json()
    
    score = data.get("brand_score")
    retries = data.get("token_stats", {}).get("retries_used")
    caption = data.get("generated_copy", {}).get("linkedin", {}).get("caption", "")
    
    output = {"score": score, "retries": retries, "caption": caption}
    with open("final_result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("Done!")

execute()
