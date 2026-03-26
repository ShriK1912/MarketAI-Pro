import os
import sys
import time

sys.path.insert(0, os.path.abspath('.'))

from services.image_service import ImageService

def main():
    print("=" * 60)
    print("SDXL Turbo Image Generation Test")
    print("Company: NovaByte Solutions")
    print("Event: Launch of AI-powered DevOps Dashboard")
    print("=" * 60)

    print("\nInitializing ImageService...")
    service = ImageService()

    prompt = (
        "A sleek futuristic dashboard interface floating in space, "
        "holographic data visualizations showing DevOps metrics, "
        "glowing blue and purple neon accents, dark background, "
        "professional tech product launch visual, 8k ultra detailed"
    )
    session_id = "test_novabyte_launch_event"

    print(f"\nGenerating hero image for prompt:\n  '{prompt}'\n")
    start_time = time.time()
    paths = service.generate_hero(prompt, session_id)
    elapsed = time.time() - start_time

    print(f"\n{'=' * 60}")
    print(f"RESULT: Generation completed in {elapsed:.1f} seconds")
    print(f"{'=' * 60}")

    all_ok = True
    for platform, path in paths.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            is_real = size > 10_000  # placeholder is usually < 10KB
            status = "REAL IMAGE" if is_real else "PLACEHOLDER (small file)"
            print(f"  {platform}: {path} ({size:,} bytes) — {status}")
            if not is_real:
                all_ok = False
        else:
            print(f"  {platform}: ERROR — file missing at {path}")
            all_ok = False

    print()
    if all_ok:
        print("SUCCESS: Real images were generated!")
    else:
        print("WARNING: Placeholder or missing images detected. Check logs above for details.")

if __name__ == "__main__":
    main()
