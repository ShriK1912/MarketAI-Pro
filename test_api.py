import httpx
import time
import json
import sys

base_url = "http://127.0.0.1:8000"

def wait_for_server():
    print("Waiting for server to start...")
    for _ in range(30):
        try:
            r = httpx.get(f"{base_url}/health", timeout=10.0)
            if r.status_code == 200:
                print("Server is up!")
                return True
        except Exception:
            time.sleep(1)
    return False

def test():
    if not wait_for_server():
        print("Server not responding.")
        sys.exit(1)

    print("\n--- Onboarding Brand ---")
    try:
        with open("test_brand_nova.txt", "rb") as f:
            files = {"file": ("test_brand_nova.txt", f, "text/plain")}
            r = httpx.post(f"{base_url}/onboard-brand", files=files, timeout=30.0)
        print("Onboard Status:", r.status_code)
        print("Brand Name:", r.json().get("brand_name"))
    except Exception as e:
        print("Error onboarding:", e)
        sys.exit(1)

    print("\n--- Generating Content ---")
    payload = {
      "feature_name": "AI Campaign Autopilot",
      "description": "A new NovaTech AI feature that automatically drafts, scores, and publishes multi-channel marketing campaigns from a single product brief — with zero manual formatting needed.",
      "target_audience": "Enterprise marketing directors and CMOs at B2B tech companies",
      "tone": "bold and strategic",
      "platforms": ["linkedin", "twitter", "instagram"],
      "brand_name": "NovaTech AI"
    }
    
    try:
        # Long timeout because the LLM might take several attempts
        r = httpx.post(f"{base_url}/generate-sync", json=payload, timeout=90.0)
        print("Generate Status:", r.status_code)
        
        data = r.json()
        print("\n--- Results ---")
        print(f"Final Brand Score : {data.get('brand_score')}/100")
        
        stats = data.get("token_stats", {})
        print(f"Retries Used      : {stats.get('retries_used')} / 2 allowed")
        print(f"Generation Time   : {stats.get('generation_time_ms', 0) / 1000:.2f} s")
        
        copy = data.get("generated_copy", {})
        print("\nLinkedIn Caption:")
        print("-" * 40)
        print(copy.get("linkedin", {}).get("caption"))
        print("-" * 40)
        
    except httpx.ReadTimeout:
        print("Generation timed out (LLM took too long). Check backend logs for progress.")
    except Exception as e:
        print("Error generating:", e)

if __name__ == "__main__":
    test()
