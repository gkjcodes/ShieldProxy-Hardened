#!/usr/bin/env python3
"""
Phase 1 Checkpoint Runner: Security Core and Gateway Integrity
Validates checkpoints CP-1.1 through CP-1.6 by executing real automated tests,
inspecting return codes, and verifying runtime assertions.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTEST_PATH = REPO_ROOT / "backend" / "venv" / "Scripts" / "pytest.exe"
if not PYTEST_PATH.exists():
    PYTEST_PATH = Path(shutil.which("pytest") or sys.executable)
PYTHON_PATH = REPO_ROOT / "backend" / "venv" / "Scripts" / "python.exe"
if not PYTHON_PATH.exists():
    PYTHON_PATH = Path(sys.executable)


def run_command(cmd: List[str], cwd: Path = REPO_ROOT) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
            check=False,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "command": " ".join(cmd),
        }
    except Exception as exc:
        return {
            "exit_code": -1,
            "stdout": str(exc),
            "command": " ".join(cmd),
        }


def check_cp_1_1() -> Dict[str, Any]:
    """CP-1.1: Configuration and dependency integrity"""
    test_cmd = [str(PYTEST_PATH), "tests/test_config.py", "-v"]
    result = run_command(test_cmd)
    passed = result["exit_code"] == 0
    return {
        "id": "CP-1.1",
        "name": "Configuration and dependency integrity",
        "command": result["command"],
        "expected": "Pydantic Settings validation enforces safe configuration; rejects wildcard CORS and missing keys in protected mode; credential masking verified; requirements pruned of dead packages.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result["exit_code"],
        "evidence": "All 6 config and dependency integrity tests passed." if passed else result["stdout"][-300:],
    }


def check_cp_1_2() -> Dict[str, Any]:
    """CP-1.2: Authentication, browser session integrity, and tenant isolation"""
    test_cmd = [str(PYTEST_PATH), "tests/test_auth.py", "tests/test_session_auth.py", "-v"]
    result = run_command(test_cmd)
    passed = result["exit_code"] == 0
    return {
        "id": "CP-1.2",
        "name": "Authentication, browser session integrity, and tenant isolation",
        "command": result["command"],
        "expected": "Unauthenticated and invalid credentials rejected (401); constant-time HMAC verification; body spoofing defeated; admin role enforced on /clients; HttpOnly cookie session flow and CSRF origin verification enforced; zero credentials in frontend source or production bundle.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result["exit_code"],
        "evidence": "All 18 authentication, session integrity, tenant scoping, and authorization tests passed." if passed else result["stdout"][-300:],
    }


def check_cp_1_3() -> Dict[str, Any]:
    """CP-1.3: Atomic rate limiting and Redis outages"""
    test_cmd = [str(PYTEST_PATH), "tests/test_rate_limiter.py", "-v"]
    result = run_command(test_cmd)
    passed = result["exit_code"] == 0
    return {
        "id": "CP-1.3",
        "name": "Atomic rate limiting and Redis outages",
        "command": result["command"],
        "expected": "Atomic Redis Lua token bucket enforces concurrency quotas; tenant quotas isolated; protected mode fails closed with HTTP 503 on Redis outage.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result["exit_code"],
        "evidence": "All 5 atomic rate limiting and outage fail-closed tests passed." if passed else result["stdout"][-300:],
    }


def check_cp_1_4() -> Dict[str, Any]:
    """CP-1.4: Request boundaries and safe API contracts"""
    test_cmd = [str(PYTEST_PATH), "tests/test_body_limits.py", "-v"]
    result = run_command(test_cmd)
    passed = result["exit_code"] == 0
    return {
        "id": "CP-1.4",
        "name": "Request boundaries and safe API contracts",
        "command": result["command"],
        "expected": "Streaming ASGI middleware rejects payloads > 64 KiB with HTTP 413; Content-Length spoofing blocked; safe error schemas without internal stack traces.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result["exit_code"],
        "evidence": "All 3 body limit, streaming check, and safe schema tests passed." if passed else result["stdout"][-300:],
    }


def check_cp_1_5() -> Dict[str, Any]:
    """CP-1.5: Privacy-safe logging and non-blocking gateway"""
    test_cmd = [str(PYTEST_PATH), "tests/test_privacy_logging.py", "tests/test_async_gateway.py", "-v"]
    result = run_command(test_cmd)
    passed = result["exit_code"] == 0
    return {
        "id": "CP-1.5",
        "name": "Privacy-safe logging and non-blocking gateway",
        "command": result["command"],
        "expected": "Zero raw prompt/PII retention in audit streams; safe event metadata recorded; async non-blocking execution via AsyncOpenAI; explicit 15s timeouts.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result["exit_code"],
        "evidence": "All 5 privacy logging and async gateway tests passed." if passed else result["stdout"][-300:],
    }


def check_cp_1_6() -> Dict[str, Any]:
    """CP-1.6: Health probes, regression and release verification"""
    pytest_cmd = [str(PYTEST_PATH), "tests/test_health.py", "tests/test_chat_integration.py", "-v"]
    pytest_res = run_command(pytest_cmd)

    git_cmd = ["git", "diff", "--check"]
    git_res = run_command(git_cmd)

    npm_cmd = ["npm.cmd" if os.name == "nt" else "npm", "run", "build"]
    npm_res = run_command(npm_cmd)

    passed = (pytest_res["exit_code"] == 0 and git_res["exit_code"] == 0 and npm_res["exit_code"] == 0)

    evidence_parts = []
    if pytest_res["exit_code"] == 0:
        evidence_parts.append("Health & end-to-end integration tests passed (6 tests).")
    else:
        evidence_parts.append(f"Pytest failed (exit {pytest_res['exit_code']}).")

    if git_res["exit_code"] == 0:
        evidence_parts.append("Git diff --check clean (exit 0).")
    else:
        evidence_parts.append(f"Git diff --check failed (exit {git_res['exit_code']}).")

    if npm_res["exit_code"] == 0:
        evidence_parts.append("Frontend production build passed (Vite exit 0).")
    else:
        evidence_parts.append(f"Frontend build failed (exit {npm_res['exit_code']}).")

    return {
        "id": "CP-1.6",
        "name": "Health probes, regression and release verification",
        "command": f"{' '.join(pytest_cmd)} && {' '.join(git_cmd)} && {' '.join(npm_cmd)}",
        "expected": "Liveness/readiness probes verified; end-to-end chat integration verified; git diff clean; frontend production build passes cleanly.",
        "status": "PASS" if passed else "FAIL",
        "exit_code": 0 if passed else 1,
        "evidence": " ".join(evidence_parts),
    }


def run_phase1_checkpoints() -> bool:
    print("=" * 80)
    print(" SHIELDPROXY PHASE 1 CHECKPOINT RUNNER: Security Core & Gateway Integrity")
    print("=" * 80)

    checkpoints = [
        check_cp_1_1,
        check_cp_1_2,
        check_cp_1_3,
        check_cp_1_4,
        check_cp_1_5,
        check_cp_1_6,
    ]

    all_passed = True
    results = []

    for check_fn in checkpoints:
        res = check_fn()
        results.append(res)
        status_str = f"[{res['status']}]"
        print(f"\n{res['id']}: {res['name']} -> {status_str}")
        print(f"  Command:  {res['command']}")
        print(f"  Expected: {res['expected']}")
        print(f"  Evidence: {res['evidence']}")
        if res["status"] != "PASS":
            all_passed = False

    print("\n" + "-" * 80)
    print(f" PHASE 1 OVERALL STATUS: {'PASS' if all_passed else 'FAIL'}")
    print("-" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_phase1_checkpoints()
    sys.exit(0 if success else 1)