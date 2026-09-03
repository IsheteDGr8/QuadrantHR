#!/usr/bin/env python3
"""OpenAPI Specification Exporter.

Extracts the OpenAPI schema from the FastAPI application and saves it
as JSON and YAML artifacts in the `openapi/` directory.
"""

import argparse
import json
import sys
from pathlib import Path

# Add root and backend to python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from backend.main import app  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def export_openapi_spec(output_dir: Path) -> dict:
    """Generate and write OpenAPI schema files.

    Args:
        output_dir: Directory where openapi.json and openapi.yaml will be written.

    Returns:
        dict: The OpenAPI schema dictionary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    openapi_schema = app.openapi()

    # Save openapi.json
    json_path = output_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"✅ Exported OpenAPI JSON spec to: {json_path}")

    # Save openapi.yaml
    if yaml is not None:
        yaml_path = output_dir / "openapi.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, sort_keys=False, default_flow_style=False)
        print(f"✅ Exported OpenAPI YAML spec to: {yaml_path}")

    return openapi_schema


def main():
    default_openapi_dir = root_dir / "openapi"
    parser = argparse.ArgumentParser(
        description="Export OpenAPI schema from TicketGenie FastAPI backend"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_openapi_dir,
        help="Directory to save openapi.json/yaml files (default: ./openapi)",
    )
    args = parser.parse_args()

    export_openapi_spec(args.output_dir)


if __name__ == "__main__":
    main()
