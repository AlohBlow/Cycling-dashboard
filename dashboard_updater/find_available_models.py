#!/usr/bin/env python
"""
Find which Claude models are actually available to this API key
"""
import sys
sys.path.insert(0, '.')
from config import ANTHROPIC_API_KEY
from anthropic import Anthropic

print("=" * 70)
print("FINDING AVAILABLE CLAUDE MODELS")
print("=" * 70)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# List of models to test (from newest to oldest, most likely to least likely)
models_to_test = [
    # Latest versions (2025)
    "claude-opus-4-20250514",
    "claude-opus-4-20250805",
    "claude-3-opus-20250219",
    "claude-opus",

    # Sonnet versions
    "claude-3-5-sonnet-20241022",
    "claude-3-sonnet-20240229",
    "claude-sonnet",

    # Haiku versions
    "claude-3-haiku-20240307",
    "claude-haiku",

    # Generic names (might resolve to latest)
    "claude-opus-latest",
    "claude-sonnet-latest",
    "claude-3",
    "claude",
]

print(f"\nTesting {len(models_to_test)} model names...\n")

working_models = []

for model in models_to_test:
    try:
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Hi"}
            ]
        )
        print(f"✓ {model:40} → SUCCESS")
        working_models.append(model)
    except Exception as e:
        error_msg = str(e)
        if "not_found" in error_msg.lower() or "404" in error_msg:
            print(f"✗ {model:40} → Not found (404)")
        elif "permission" in error_msg.lower() or "access" in error_msg.lower():
            print(f"✗ {model:40} → No access")
        else:
            print(f"✗ {model:40} → Error: {error_msg[:40]}")

print("\n" + "=" * 70)
if working_models:
    print(f"\n✓ FOUND {len(working_models)} WORKING MODEL(S):\n")
    for model in working_models:
        print(f"   → {model}")
    print(f"\nUse this model in your code!")
else:
    print("\n✗ No working models found. Your API key might have access restrictions.")
    print("   Check https://console.anthropic.com/account/billing/overview")

print("\n" + "=" * 70)
