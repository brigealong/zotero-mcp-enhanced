from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abbyy_mcp.abbyy_runner import FineCmdRunner
from abbyy_mcp.config import AppConfig
from abbyy_mcp.job_store import JobStore
from abbyy_mcp.runner import StubOcrRunner
from abbyy_mcp.service import OcrJobService


def wait_for_result(service: OcrJobService, job_id: str, timeout_seconds: float) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    result = service.get_ocr_job_result(job_id)
    while result["status"] in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.2)
        result = service.get_ocr_job_result(job_id)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ABBYY MCP smoke tests")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--runner", choices=["stub", "abbyy"], default="stub")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--wait-timeout", type=float, default=60.0)
    parser.add_argument("--job-timeout", type=int, default=None)
    parser.add_argument("--base-dir", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()

    config = AppConfig.from_base_dir(args.base_dir)
    runner = (
        FineCmdRunner(finecmd_path=config.finecmd_path, timeout_seconds=int(args.timeout))
        if args.runner == "abbyy"
        else StubOcrRunner()
    )
    service = OcrJobService(config=config, store=JobStore(config), runner=runner)

    summaries: list[dict[str, object]] = []
    for index in range(args.rounds):
        submission = service.submit_pdf_ocr(
            source_pdf_path=args.pdf,
            target_item_key=f"SMOKE_ITEM_{index + 1}",
            source_attachment_key=f"SMOKE_ATTACHMENT_{index + 1}",
            timeout_seconds=args.job_timeout,
            job_label=f"{args.runner}-round-{index + 1}",
        )
        result = wait_for_result(service, submission["job_id"], args.wait_timeout)
        payload = {
            "round": index + 1,
            "job_id": submission["job_id"],
            "status": result["status"],
            "output_pdf_path": result["output_pdf_path"],
        }
        summaries.append(payload)
        if not args.keep_artifacts:
            service.cleanup_ocr_job(submission["job_id"], keep_logs=result["status"] != "succeeded")
            payload["cleaned"] = True
        else:
            payload["cleaned"] = False

    results_path = config.base_dir / "outputs" / f"smoke-{args.runner}-results.json"
    results_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(results_path)


if __name__ == "__main__":
    main()
