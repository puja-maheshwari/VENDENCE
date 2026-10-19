"""Prepare a runner manifest for the three shipped PDF scenarios."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.testing_cases import fixture_manifest


def main():
    manifest = fixture_manifest()
    for case in manifest["scenarios"]:
        for field in ("gst_path", "bank_path"):
            if not Path(case[field]).is_file():
                raise SystemExit("Missing PDF fixture. Restore the testing folder from the source package.")
    target = ROOT / "tmp/qa_inputs/three_case_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2))
    print("Three PDF scenarios; no applications changed.")
    print(target)


if __name__ == "__main__":
    main()
