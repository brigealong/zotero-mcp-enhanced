from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OCRMYPDF_PATH = Path("ocrmypdf")


def discover_ocrmypdf_path() -> Path:
    env_override = os.environ.get("OCRMYPDF_PATH")
    if env_override:
        return Path(env_override)

    appdata = os.environ.get("APPDATA")
    if appdata:
        python_root = Path(appdata) / "Python"
        if python_root.exists():
            candidates = sorted(python_root.glob("Python*/Scripts/ocrmypdf.exe"), reverse=True)
            if candidates:
                return candidates[0]

    return DEFAULT_OCRMYPDF_PATH


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    jobs_dir: Path
    ocrmypdf_path: Path
    max_workers: int = 1
    command_timeout_seconds: int = 600

    @classmethod
    def from_base_dir(
        cls,
        base_dir: Path,
        *,
        ocrmypdf_path: Path | None = None,
        max_workers: int = 1,
        command_timeout_seconds: int = 7200,
    ) -> "AppConfig":
        resolved_base = Path(base_dir)
        effective_ocrmypdf_path = Path(ocrmypdf_path) if ocrmypdf_path is not None else discover_ocrmypdf_path()
        return cls(
            base_dir=resolved_base,
            jobs_dir=resolved_base / "outputs" / "jobs",
            ocrmypdf_path=effective_ocrmypdf_path,
            max_workers=max_workers,
            command_timeout_seconds=command_timeout_seconds,
        )
