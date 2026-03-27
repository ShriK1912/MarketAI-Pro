import time
import httpx
import sys

def test_mistral():
    print("Testing Mistral on Ollama...")
    start = time.time()
    try:
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "mistral",
            "prompt": "Write a 50 word marketing blurb for NovaTech AI.",
            "stream": False
        }, timeout=300.0)
        
        elapsed = time.time() - start
        
        if r.status_code == 200:
            print(f"Success! Time taken: {elapsed:.2f} seconds")
            print("Response:", r.json().get("response"))
        else:
            print(f"Error {r.status_code}: {r.text}")
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    test_mistral()
