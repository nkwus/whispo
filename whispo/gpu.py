"""Wrappers around `nvidia-smi` for the GPU pane.

Returns plain dicts so the widget layer stays agnostic about parsing.
"""

import subprocess
from pathlib import Path


def _smi(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["nvidia-smi", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def gpu_stats() -> dict | None:
    """Return {used, free, total (MiB), processes: [{pid, name, mem}]} or None."""
    mem = _smi([
        "--query-gpu=memory.used,memory.free,memory.total",
        "--format=csv,noheader,nounits",
    ])
    if mem is None:
        return None
    try:
        used, free, total = (int(x.strip()) for x in mem.split(","))
    except ValueError:
        return None

    procs_raw = _smi([
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ]) or ""

    processes: list[dict] = []
    for line in procs_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            mem_mib = int(parts[2])
        except ValueError:
            mem_mib = 0
        processes.append({
            "pid": parts[0],
            "name": Path(parts[1]).name,
            "mem": mem_mib,
        })
    return {"used": used, "free": free, "total": total, "processes": processes}
