"""Собирает архив проекта dist/architecture-insuretech.zip из файлов, отслеживаемых git.

Служебные каталоги и файлы, исключенные .gitignore, в архив не попадают.
"""

import subprocess
import sys
import zipfile

from _common import ROOT, load_config


def tracked_files():
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    return [name for name in output.decode("utf-8").split("\0") if name]


def main():
    name = load_config()["repo"]["name"]
    target = ROOT / "dist" / f"{name}.zip"
    target.parent.mkdir(exist_ok=True)
    files = tracked_files()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(ROOT / relative, f"{name}/{relative}")
    print(f"{target.relative_to(ROOT)}: {len(files)} файлов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
