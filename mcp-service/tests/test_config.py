from pathlib import Path

from abbyy_mcp.config import AppConfig


def test_config_uses_task_local_jobs_directory() -> None:
    config = AppConfig.from_base_dir(Path("C:/work/abbyy-task"))

    assert config.jobs_dir == Path("C:/work/abbyy-task/outputs/jobs")
    assert config.finecmd_path.name == "FineCmd.exe"
    assert config.max_workers == 1
    assert config.command_timeout_seconds == 7200
