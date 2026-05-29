"""
AI Daily Digest - Main entry point.
Fetches AI news from multiple sources, summarizes with AI, and saves outputs.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from sources import fetch_all
from summarize import summarize
from generate_site import generate_site


def send_to_buttondown(subject: str, markdown: str) -> None:
    """Publish the digest as a Buttondown email (sends to all subscribers)."""
    api_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not api_key:
        print("[Buttondown] BUTTONDOWN_API_KEY not set, skipping.")
        return

    resp = requests.post(
        "https://api.buttondown.email/v1/emails",
        headers={
            "Authorization": f"Token {api_key}",
            "X-Buttondown-Live-Dangerously": "true",
        },
        json={
            "subject": subject,
            "body": markdown,
            "status": "about_to_send",  # queues for immediate send
            "email_type": "public",    # visible in archive
        },
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"[Buttondown] Sent! Email id: {resp.json().get('id')}")
    else:
        print(f"[Buttondown] Failed {resp.status_code}: {resp.text[:200]}")


def main():
    # Use Beijing time for date
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz)
    date_str = today.strftime("%Y-%m-%d")

    print(f"=== AI Daily Digest for {date_str} ===\n")

    # Step 1: Fetch data from all sources
    print("[Step 1] Fetching data from sources...")
    data = fetch_all()

    total = sum(len(v) for v in data.values())
    print(f"\nTotal items fetched: {total}")

    if total == 0:
        print("No items fetched. Exiting.")
        sys.exit(0)

    # Step 2: Save raw fetched data for traceability
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    raw_file = data_dir / f"{date_str}.raw.json"
    raw_payload = {
        "date": date_str,
        "generated_at": today.isoformat(),
        "counts": {key: len(value) for key, value in data.items()},
        "items": data,
    }
    raw_file.write_text(
        json.dumps(raw_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[Step 2] Saved raw data to {raw_file}")

    # Step 3: AI summarization
    print("\n[Step 3] Generating AI summary...")
    markdown = summarize(data, date_str)

    # Step 4: Save daily markdown
    output_dir = Path(__file__).parent.parent / "daily"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"{date_str}.md"

    output_file.write_text(markdown, encoding="utf-8")
    print(f"\n[Step 4] Saved to {output_file}")

    # Step 5: Rebuild static site
    print("\n[Step 5] Rebuilding static site...")
    generate_site(root=Path(__file__).parent.parent)
    print("  Site rebuilt → docs/")

    # Step 6: Send to Buttondown subscribers
    print("\n[Step 6] Sending to Buttondown subscribers...")
    subject = f"AI Daily Digest · {date_str}"
    send_to_buttondown(subject, markdown)

    print("Done!")


if __name__ == "__main__":
    main()
