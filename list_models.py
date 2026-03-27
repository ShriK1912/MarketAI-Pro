import os
from dotenv import load_dotenv
import requests
import json

load_dotenv("c:\\Users\\Lenovo\\Desktop\\AISSM\\.env")
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("API key not found in .env")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    for model in data.get("models", []):
        if "imagen" in model.get("name", "").lower():
            print(model.get("name"), "-", model.get("supportedGenerationMethods"))
else:
    print(f"Failed to list models: {response.status_code}")
    print(response.text)
