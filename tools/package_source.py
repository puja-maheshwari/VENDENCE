"""Prepare a local, explicitly whitelisted source package; never publish it."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    name = "vendence-source-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = ROOT / "dist" / name
    sources = list(ROOT.glob("*.py")) + list(ROOT.glob("*.md"))
    sources += [ROOT / filename for filename in (
        "requirements.txt", "requirements-lock.txt", ".env.example", ".gitignore",
        ".streamlit/config.toml") if (ROOT / filename).is_file()]
    for folder in ("tests", "tools"):
        sources.extend((ROOT / folder).rglob("*.py"))
    for path in (ROOT / "testing").rglob("*"):
        if path.is_file() and path.suffix == ".pdf":
            sources.append(path)
    for source in sorted(set(sources)):
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    archive = ROOT / "dist" / (name + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for source in sorted(destination.rglob("*")):
            if source.is_file():
                output.write(source, source.relative_to(destination.parent))
    print(f"Prepared {len(set(sources))} whitelisted files. Nothing was published.")
    print(archive)


if __name__ == "__main__":
    main()
