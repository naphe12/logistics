import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
RELEASE_CHECK = BACKEND_DIR / "scripts" / "release_check.py"


def _venv_python_path() -> Path:
    candidates = [
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
        BACKEND_DIR / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find backend virtualenv python in backend/.venv")


def _run_step(name: str, cmd: list[str], cwd: Path) -> dict:
    print(f"\n=== {name} ===")
    print(" ".join(cmd))
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    duration_ms = int((time.time() - started) * 1000)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr.rstrip())
    return {
        "name": name,
        "command": cmd,
        "cwd": str(cwd),
        "return_code": proc.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
        "ok": proc.returncode == 0,
    }


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Production gate: migrations + release checks + JSON report.")
    parser.add_argument("--base-url", default="", help="API base URL for smoke API (optional)")
    parser.add_argument("--token", default="", help="Bearer token for smoke API (optional)")
    parser.add_argument("--sender-phone", default="+25762009001", help="Smoke sender phone")
    parser.add_argument("--receiver-phone", default="+25762009002", help="Smoke receiver phone")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip alembic upgrade head")
    parser.add_argument("--skip-backend-compile", action="store_true", help="Forwarded to release_check")
    parser.add_argument("--skip-frontend-build", action="store_true", help="Forwarded to release_check")
    parser.add_argument("--skip-smoke", action="store_true", help="Forwarded to release_check")
    parser.add_argument("--run-api-tests", action="store_true", help="Forwarded to release_check")
    parser.add_argument(
        "--json-out",
        default=str(BACKEND_DIR / "scripts" / "last_prod_gate_report.json"),
        help="Path to JSON report output",
    )
    args = parser.parse_args()

    try:
        venv_python = _venv_python_path()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    started_at = datetime.now(UTC).isoformat()
    steps: list[dict] = []

    if not args.skip_migrate:
        steps.append(
            _run_step(
                "Alembic Upgrade Head",
                [str(venv_python), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
                cwd=ROOT_DIR,
            )
        )
        if not steps[-1]["ok"]:
            report = {
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "reason": "migration_failed",
                "steps": steps,
            }
            _write_report(Path(args.json_out), report)
            print(f"\nPROD GATE FAILED (migration). Report: {args.json_out}")
            return 1

    release_cmd = [str(venv_python), str(RELEASE_CHECK)]
    if args.base_url:
        release_cmd.extend(["--base-url", args.base_url])
    if args.token:
        release_cmd.extend(["--token", args.token])
    if args.sender_phone:
        release_cmd.extend(["--sender-phone", args.sender_phone])
    if args.receiver_phone:
        release_cmd.extend(["--receiver-phone", args.receiver_phone])
    if args.skip_backend_compile:
        release_cmd.append("--skip-backend-compile")
    if args.skip_frontend_build:
        release_cmd.append("--skip-frontend-build")
    if args.skip_smoke:
        release_cmd.append("--skip-smoke")
    if args.run_api_tests:
        release_cmd.append("--run-api-tests")

    steps.append(_run_step("Release Check", release_cmd, cwd=ROOT_DIR))

    ok = all(step["ok"] for step in steps)
    report = {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "steps": steps,
    }
    _write_report(Path(args.json_out), report)
    if ok:
        print(f"\nPROD GATE OK. Report: {args.json_out}")
        return 0
    print(f"\nPROD GATE FAILED. Report: {args.json_out}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
