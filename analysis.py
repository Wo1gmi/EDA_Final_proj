import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import resource
except ImportError:
    resource = None

__author__ = "Анастасия Казакова; Степан Селезнев; Светлана Калошкина"

ROOT = Path(__file__).resolve().parent
SCRIPTS = [
    "00_download.py",
    "01_prepare.py",
    "02_descriptive.py",
    "03_var.py",
    "04_garch.py",
    "05_robustness.py",
    "06_outofsample.py",
]
PACKAGES = ["pandas", "numpy", "requests", "statsmodels", "arch", "matplotlib", "pyarrow", "scipy"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hashes(paths):
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def peak_child_memory():
    if resource is None:
        return None
    amount = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return amount / (1024 ** 2 if sys.platform == "darwin" else 1024)


def main():
    started = time.perf_counter()
    run_utc = datetime.now(timezone.utc).isoformat()
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    env = os.environ.copy()
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]:
        env[name] = "8"
    env["MPLBACKEND"] = "Agg"
    env.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
    env["PYTHONUTF8"] = "1"
    code_paths = [ROOT / "analysis.py", ROOT / "verify_results.py", ROOT / "requirements.txt", *(ROOT / "src").glob("*.py")]
    initial_code_hashes = file_hashes(code_paths)
    timings = []
    with (output / "run.log").open("w", encoding="utf-8") as log:
        for script in SCRIPTS:
            step_started = time.perf_counter()
            label = f"\n{script}\n"
            print(label, end="", flush=True)
            log.write(label)
            result = subprocess.run(
                [sys.executable, str(ROOT / "src" / script)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            print(result.stdout, end="", flush=True)
            log.write(result.stdout)
            timings.append({"script": script, "seconds": time.perf_counter() - step_started, "returncode": result.returncode})
            if result.returncode:
                raise RuntimeError(f"Расчёт остановлен: {script}, код {result.returncode}. Подробности в output/run.log.")
    if file_hashes(code_paths) != initial_code_hashes:
        raise RuntimeError("Файлы кода изменились во время расчёта. Повторите запуск после завершения редактирования.")
    results = [*(ROOT / "data" / "processed").glob("*")]
    for folder in ["tables", "figures", "models"]:
        results.extend((output / folder).glob("*"))
    manifest = {
        "schema_version": 1,
        "authors": __author__.split("; "),
        "run_utc": run_utc,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "numerical_thread_limit": 8,
            "peak_child_rss_mib": peak_child_memory(),
            "exact_8cpu_16gb_hardware_test": False,
            "versions": {name: importlib.metadata.version(name) for name in PACKAGES},
        },
        "scripts": timings,
        "source_files": file_hashes((ROOT / "data" / "raw").glob("*.csv")),
        "code_files": initial_code_hashes,
        "results_files": file_hashes(results),
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nПолный расчёт: {manifest['elapsed_seconds']:.2f} с. Манифест: output/run_manifest.json.")


if __name__ == "__main__":
    main()
