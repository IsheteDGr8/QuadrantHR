"""Command-line script to trigger daily digest email dispatch."""

import logging
import sys

from dotenv import load_dotenv

from services.daily_digest_service import send_daily_admin_digest

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    load_dotenv()
    print("Running Daily Admin Digest dispatch...")
    res = send_daily_admin_digest()
    print("Result:", res)
    sys.exit(
        0 if res.get("status") == "success" or res.get("dispatched_count", 0) > 0 else 1
    )
