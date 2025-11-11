#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py — Launch orchestrator, API gateway, and Gradio frontend.
- Uses module invocations so relative imports work
- Waits on health/ready checks
- Tails logs on failure
"""
import subprocess
import time
import os
import sys
import signal
from urllib.request import urlopen, Request
from urllib.error import URLError

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "Part_2", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_path(name): return os.path.join(LOG_DIR, f"{name}.log")

SERVICES = [
    {
        "name": "orchestrator",
        "cmd": [sys.executable, "-m", "uvicorn", "Part_2.orchestrator.app:app", "--port", "8001", "--reload"],
        "health": "http://127.0.0.1:8001/health",
        "log": log_path("orchestrator"),
        "cwd": ROOT,
    },
    {
        "name": "api-gateway",
        "cmd": [sys.executable, "-m", "uvicorn", "Part_2.api_gateway.app:app", "--port", "8000", "--reload"],
        "health": "http://127.0.0.1:8000/health",
        "log": log_path("api-gateway"),
        "cwd": ROOT,
    },
    {
        "name": "frontend",
        # IMPORTANT: run as a module so relative imports (..core_models) work
        "cmd": [sys.executable, "-m", "Part_2.fronted.ui_gradio"],
        "health": "http://127.0.0.1:7860/",
        "log": log_path("frontend"),
        "cwd": ROOT,
    },
]

procs = []

def launch(svc):
    print(f"▶ Launching {svc['name']}: {' '.join(svc['cmd'])}")
    f = open(svc["log"], "w")
    p = subprocess.Popen(svc["cmd"], cwd=svc["cwd"], stdout=f, stderr=subprocess.STDOUT)
    svc["file"] = f
    svc["proc"] = p
    procs.append(svc)

def wait_ready(url, name, timeout=30.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Some endpoints require a GET with a header to avoid 403s on dev
            req = Request(url, headers={"User-Agent": "run_all"})
            with urlopen(req, timeout=2) as r:
                if 200 <= r.status < 500:  # Gradio root '/' may return 200/404—both mean server is up
                    print(f"✓ {name} is up: {url}")
                    return True
        except URLError:
            pass
        time.sleep(0.5)
    print(f"✗ {name} did not become ready in {timeout:.0f}s: {url}")
    return False

def tail_log(path, n=40):
    print(f"\n— Last {n} lines of {path} —")
    try:
        with open(path, "r") as f:
            lines = f.readlines()[-n:]
            for line in lines:
                print(line.rstrip())
    except Exception as e:
        print(f"(could not read log: {e})")

def stop_all():
    print("\n⏹ Stopping all services…")
    for svc in reversed(procs):
        p = svc.get("proc")
        f = svc.get("file")
        try:
            if p and p.poll() is None:
                p.terminate()
        except Exception:
            pass
        if f:
            try: f.flush(); f.close()
            except Exception: pass
    # Give them a moment to exit, then kill leftovers
    time.sleep(1.5)
    for svc in reversed(procs):
        p = svc.get("proc")
        if p and p.poll() is None:
            try: p.kill()
            except Exception: pass
    print("✅ All services stopped.")

if __name__ == "__main__":
    try:
        for svc in SERVICES:
            launch(svc)
            # small stagger helps uvicorn file watchers
            time.sleep(1.0)

        # Wait for readiness in dependency order
        ok = True
        ok &= wait_ready(SERVICES[0]["health"], SERVICES[0]["name"])  # orchestrator
        ok &= wait_ready(SERVICES[1]["health"], SERVICES[1]["name"])  # api-gateway
        ok &= wait_ready(SERVICES[2]["health"], SERVICES[2]["name"])  # frontend

        if not ok:
            # Show logs to help debug and exit non-zero
            for svc in SERVICES:
                tail_log(svc["log"])
            stop_all()
            sys.exit(1)

        print("\n🚀 All services launched.")
        print("Frontend: http://127.0.0.1:7860")
        print("API:      http://127.0.0.1:8000")
        print("Orch:     http://127.0.0.1:8001")
        print("\nPress Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all()
    except Exception as e:
        print(f"⚠️ Error: {e}")
        for svc in SERVICES:
            tail_log(svc["log"])
        stop_all()
        sys.exit(1)
