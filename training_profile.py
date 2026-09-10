"""Create a new isolated training save root; never copy or overwrite user saves."""
import argparse
import json
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parent


def prepare(name, workspace=ROOT):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", name):
        raise ValueError("Profile name must be 1..40 lowercase letters, digits, _ or -")
    base = workspace.resolve() / "profiles"
    root = base / name
    # Existing profiles must be explicitly reused, never reset by this command.
    if base.is_symlink() or base.resolve() != base or root.exists():
        raise ValueError("Profile exists or profiles directory is redirected")
    root.mkdir(parents=True)
    for folder in ("Players", "Worlds", "Mods"):
        (root / folder).mkdir()
    marker = {"schema": 1, "purpose": "training", "profileId": str(uuid.uuid4()),
              "saveRoot": str(root), "saveNamePrefix": "TM-Training-"}
    (root / "terramaster-training.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    (root / "Mods" / "enabled.json").write_text('["TerraBridge"]\n', encoding="utf-8")
    return marker


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", default="training-m0")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.name), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Profile not created: {exc}\n")
