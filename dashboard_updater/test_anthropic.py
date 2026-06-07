#!/usr/bin/env python
"""
Test Anthropic API connectivity and model availability
"""
import sys
sys.path.insert(0, '.')
from config import ANTHROPIC_API_KEY

print("=" * 70)
print("ANTHROPIC API TEST")
print("=" * 70)

print(f"\n1. API Key:")
print(f"   Format: {ANTHROPIC_API_KEY[:20]}...{ANTHROPIC_API_KEY[-10:]}")
print(f"   Valid: {'Yes' if ANTHROPIC_API_KEY.startswith('sk-ant-') else 'No'}")

try:
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    print(f"\n2. Anthropic client initialized ✓")

    print(f"\n3. Testing simple message (using claude-3-5-sonnet-20241022)...")

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=50,
        messages=[
            {"role": "user", "content": "Say 'Hello' and nothing else."}
        ]
    )

    print(f"   ✓ Success!")
    print(f"   Response: {message.content[0].text}")

except Exception as e:
    print(f"   ✗ Error: {e}")
    print(f"   Type: {type(e).__name__}")

    # Try to get more details
    if hasattr(e, 'response'):
        print(f"   Status: {e.response.status_code}")
        print(f"   Body: {e.response.text[:200]}")

print("\n" + "=" * 70)
