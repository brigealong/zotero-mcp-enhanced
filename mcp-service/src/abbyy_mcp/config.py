from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_FINECMD_PATH = Path(r"C:\Program Files (x86)\ABBYY FineReader 15\FineCmd.exe")


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    jobs_dir: Path
    finecmd_path: Path
    max_workers: int = 1
    command_timeout_seconds: int = 600

    @classmethod
    def from_base_dir(
        cls,
        base_dir: Path,
        *,
        finecmd_path: Path = DEFAULT_FINECMD_PATH,
        max_workers: int = 1,
        command_timeout_seconds: int = 7200,
    ) -> "AppConfig":
        resolved_base = Path(base_dir)
        return cls(
            base_dir=resolved_base,
            jobs_dir=resolved_base / "outputs" / "jobs",
            finecmd_path=finecmd_path,
            max_workers=max_workers,
            command_timeout_seconds=command_timeout_seconds,
        )
