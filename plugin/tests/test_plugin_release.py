from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugin"
BUILD_SCRIPT = PLUGIN_DIR / "build-plugin.ps1"
DIST_XPI = PLUGIN_DIR / "dist" / "zotero-mcp-enhanced.xpi"


def parse_ftl_message_ids(path: Path) -> set[str]:
    message_ids: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("."):
            continue
        if "=" not in line:
            continue
        message_id = line.split("=", 1)[0].strip()
        message_ids.add(message_id)
    return message_ids


def test_build_script_creates_installable_xpi() -> None:
    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
        ],
        check=True,
        cwd=PLUGIN_DIR,
    )

    assert DIST_XPI.exists()
    with zipfile.ZipFile(DIST_XPI) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "bootstrap.js" in names
    assert "locale/en-US/markdownreadercopy-preferences.ftl" in names
    assert "locale/zh-CN/markdownreadercopy-preferences.ftl" in names


def test_locale_message_ids_match_between_english_and_chinese() -> None:
    english_files = sorted((PLUGIN_DIR / "locale" / "en-US").glob("*.ftl"))
    chinese_files = sorted((PLUGIN_DIR / "locale" / "zh-CN").glob("*.ftl"))

    assert [path.name for path in english_files] == [path.name for path in chinese_files]

    for english_path in english_files:
        chinese_path = PLUGIN_DIR / "locale" / "zh-CN" / english_path.name
        assert parse_ftl_message_ids(english_path) == parse_ftl_message_ids(chinese_path)


def test_remi_intro_copy_includes_chinese_translation() -> None:
    preferences_en = (PLUGIN_DIR / "locale" / "en-US" / "markdownreadercopy-preferences.ftl").read_text(
        encoding="utf-8"
    )
    preferences_zh = (PLUGIN_DIR / "locale" / "zh-CN" / "markdownreadercopy-preferences.ftl").read_text(
        encoding="utf-8"
    )

    assert "Remi" in preferences_en
    assert "local bridge" in preferences_en
    assert "本地桥接器" in preferences_en
    assert "Remi" in preferences_zh
    assert "本地桥接器" in preferences_zh
