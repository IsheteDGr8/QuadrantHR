#!/usr/bin/env python3
"""
scripts/fetch_secrets.py - Fetch Azure Key Vault secrets into local .env file.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fetch_secrets import main  # noqa: E402

if __name__ == "__main__":
    main()
