# Backend Scripts

## Smoke API

Run end-to-end smoke checks against a running backend:

```bash
python scripts/smoke_api.py --base-url https://your-api.example.com --token <ACCESS_TOKEN>
```

Notes:
- Use an `admin` or `hub` access token so all protected routes are testable.
- The script creates test data (shipment, payment, incident).
- Non-zero exit code means failure.

## Release Check (Backend + Frontend + Optional Smoke)

Run all checks in one command:

```bash
python scripts/release_check.py
```

Run with smoke API against deployed backend:

```bash
python scripts/release_check.py --base-url https://your-api.example.com --token <ACCESS_TOKEN>
```

PowerShell with backend venv:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\release_check.py --base-url https://your-api.example.com --token <ACCESS_TOKEN>
```

## Prod Gate (Migrations + Release Check + JSON Report)

Run full production gate:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\prod_gate.py --base-url https://your-api.example.com --token <ACCESS_TOKEN>
```

Local run without migration/smoke:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\prod_gate.py --skip-migrate --skip-smoke
```

Default report path:

`backend/scripts/last_prod_gate_report.json`
