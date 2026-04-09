from pathlib import Path

from zotero_mcp_enhanced_service.config import AppConfig


def test_config_uses_task_local_jobs_directory() -> None:
    config = AppConfig.from_base_dir(Path("C:/example-workspace/pdf-task"))

    assert config.jobs_dir == Path("C:/example-workspace/pdf-task/outputs/jobs")
    assert config.ocrmypdf_path.name in {"ocrmypdf", "ocrmypdf.exe"}
    assert config.max_workers == 1
    assert config.command_timeout_seconds == 7200


def test_config_prefers_env_override_for_ocrmypdf(monkeypatch) -> None:
    monkeypatch.setenv("OCRMYPDF_PATH", r"C:\Tools\ocrmypdf.exe")

    config = AppConfig.from_base_dir(Path("C:/example-workspace/pdf-task"))

    assert config.ocrmypdf_path == Path(r"C:\Tools\ocrmypdf.exe")


def test_config_discovers_user_script_install_when_env_missing(monkeypatch, tmp_path: Path) -> None:
    appdata = tmp_path / "AppData" / "Roaming"
    scripts_dir = appdata / "Python" / "Python312" / "Scripts"
    scripts_dir.mkdir(parents=True)
    discovered = scripts_dir / "ocrmypdf.exe"
    discovered.write_text("", encoding="utf-8")
    monkeypatch.delenv("OCRMYPDF_PATH", raising=False)
    monkeypatch.setenv("APPDATA", str(appdata))

    config = AppConfig.from_base_dir(Path("C:/example-workspace/pdf-task"))

    assert config.ocrmypdf_path == discovered
