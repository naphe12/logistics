import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def _venv_python_path() -> Path:
    candidates = [
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
        BACKEND_DIR / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find backend virtualenv python in backend/.venv")


def _run(cmd: list[str], cwd: Path, label: str) -> None:
    print(f"\n=== {label} ===")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _npm_executable() -> str:
    if sys.platform.startswith("win"):
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release checks for backend + frontend.")
    parser.add_argument("--base-url", default="", help="API base URL for smoke API (optional)")
    parser.add_argument("--token", default="", help="Bearer token for smoke API (optional)")
    parser.add_argument("--sender-phone", default="+25762009001", help="Smoke sender phone")
    parser.add_argument("--receiver-phone", default="+25762009002", help="Smoke receiver phone")
    parser.add_argument("--skip-backend-compile", action="store_true", help="Skip backend compile check")
    parser.add_argument("--skip-frontend-build", action="store_true", help="Skip frontend production build")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke API call")
    parser.add_argument("--run-api-tests", action="store_true", help="Run pytest API tests (requires pytest + env vars)")
    args = parser.parse_args()

    try:
        venv_python = _venv_python_path()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    try:
        if not args.skip_backend_compile:
            _run(
                [str(venv_python), "-m", "compileall", "backend/app", "backend/scripts"],
                cwd=ROOT_DIR,
                label="Backend Compile",
            )

        if not args.skip_frontend_build:
            _run([_npm_executable(), "run", "build"], cwd=FRONTEND_DIR, label="Frontend Build")

        if args.run_api_tests:
            _run(
                [str(venv_python), "-m", "pytest"],
                cwd=BACKEND_DIR,
                label="Pytest API",
            )

        should_run_smoke = (not args.skip_smoke) and bool(args.base_url) and bool(args.token)
        if should_run_smoke:
            _run(
                [
                    str(venv_python),
                    "backend/scripts/smoke_api.py",
                    "--base-url",
                    args.base_url,
                    "--token",
                    args.token,
                    "--sender-phone",
                    args.sender_phone,
                    "--receiver-phone",
                    args.receiver_phone,
                ],
                cwd=ROOT_DIR,
                label="Smoke API",
            )
        elif not args.skip_smoke:
            print("\n=== Smoke API ===")
            print("Skipped (missing --base-url or --token).")

        print("\nRELEASE CHECK OK")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"\nRELEASE CHECK FAILED (exit={exc.returncode})")
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
