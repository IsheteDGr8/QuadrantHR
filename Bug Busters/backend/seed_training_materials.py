"""One-time (or whenever-you-have-a-new-document) script: uploads a
training/handbook file straight into blob storage.

This exists specifically so nobody has to build an HR-facing "upload
materials" page - per direction, HR shouldn't be the one doing this at
all. Whoever administers the org's content runs this script locally
against their own files; it calls the same repository/agent code the
(HR-only) POST /training/{org_id}/upload endpoint uses, just without
going through the API or any role check.

Usage:
    python seed_training_materials.py <org_id> <file_path> [file_path ...]

Title/description/category are auto-generated from each document's
content (same agent as the upload endpoint) unless you pass --title/
--description/--category, which only apply when uploading a single file.

Needs the app's real Azure OpenAI + storage settings in the environment
(same as running the app itself) - see .env.example.
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from document_parser import extract_text_from_upload, UnsupportedFileTypeError
from training_agent import generate_metadata, TrainingAgentError
from training_repository import create_file_resource

SEEDED_BY = "seed-script"


def seed_file(org_id: str, file_path: Path, title: str | None, description: str | None, category: str | None):
    file_bytes = file_path.read_bytes()

    if not file_bytes:
        print(f"  Skipped {file_path.name}: file is empty.")
        return

    if not (title and description and category):
        try:
            extracted_text = extract_text_from_upload(file_path.name, file_bytes)
            generated = generate_metadata(file_path.name, extracted_text)
        except UnsupportedFileTypeError as e:
            print(f"  Skipped {file_path.name}: {e}")
            return
        except TrainingAgentError as e:
            print(f"  Skipped {file_path.name}: couldn't auto-generate metadata ({e}). Re-run with --title/--description/--category to set it manually.")
            return

        title = title or generated["title"]
        description = description or generated["description"]
        category = category or generated["category"]

    resource = create_file_resource(
        org_id,
        title=title,
        description=description,
        category=category,
        original_filename=file_path.name,
        file_bytes=file_bytes,
        uploaded_by_user_id=SEEDED_BY,
    )

    print(f"  Uploaded {file_path.name} -> \"{resource.title}\" ({resource.category})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("org_id")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--title", default=None, help="Only valid with a single file.")
    parser.add_argument("--description", default=None, help="Only valid with a single file.")
    parser.add_argument("--category", default=None, help="Only valid with a single file.")
    args = parser.parse_args()

    if len(args.files) > 1 and (args.title or args.description or args.category):
        parser.error("--title/--description/--category can only be used with a single file.")

    print(f"Seeding {len(args.files)} file(s) into org '{args.org_id}':")

    for file_path in args.files:
        if not file_path.is_file():
            print(f"  Skipped {file_path}: not a file.")
            continue

        seed_file(args.org_id, file_path, args.title, args.description, args.category)


if __name__ == "__main__":
    main()
