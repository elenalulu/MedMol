"""Parallel-download big cp312 win_amd64 wheels from PyPI (single-stream pip is ~20 KB/s).
Run: python download_pypi_wheels.py --dest wheelhouse/
Then: pip install boltz --find-links wheelhouse/   (small pkgs still fetched online)
"""
import argparse, json, pathlib, urllib.request, concurrent.futures as cf, sys, time, threading
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from download_weights_parallel import fetch_range, head_total  # reuse range logic

PKGS = [
    ("torch", "2.15.0"),
    ("rdkit", "2026.9.2"),
    ("scipy", "1.13.1"),
    ("pandas", "3.1.1"),
    ("scikit-learn", "1.6.1"),
    ("pillow", None),
]

lock = threading.Lock()
progress = {"bytes": 0, "t0": time.time()}

def report(n):
    with lock:
        progress["bytes"] += n
        b, el = progress["bytes"], max(time.time() - progress["t0"], 1)
        if b % (32 << 20) < (1 << 20):
            print(f"    total {b/1e6:.0f} MB | {b/1e6/el:.1f} MB/s", flush=True)

def _get_json(url, retries=4, timeout=15):
    import urllib.error
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"    api attempt {i+1} failed: {e}", flush=True)
            time.sleep(2 * (i + 1))
    return None

def pick_wheel(pkg, ver):
    api = f"https://pypi.org/pypi/{pkg}/{ver}/json" if ver else f"https://pypi.org/pypi/{pkg}/json"
    d = _get_json(api)
    if d is None:
        return None
    ver = d["info"]["version"] if not ver else ver
    files = d["urls"]
    best = None
    for f in files:
        fn = f["filename"]
        if fn.endswith(".whl") and ("cp312-cp312-win_amd64" in fn or "py3-none-any" in fn or "py2.py3-none-any" in fn or "cp3-abi3-win_amd64" in fn or "abi3-win_amd64" in fn):
            score = 0 if "cp312-cp312-win_amd64" in fn else (1 if "abi3" in fn else 2)
            if best is None or score < best[0]:
                best = (score, f["url"], fn, f["size"])
    return best

def dl(url, dest):
    total = head_total(url)
    tmp = dest.with_suffix(".part")
    start = 0
    if tmp.exists() and tmp.stat().st_size <= total:
        start = tmp.stat().st_size  # sequential resume with parallel subrange batches
    if start >= total:
        tmp.rename(dest); return
    ranges = [(s, min(s + 32 * (1 << 20) - 1, total - 1)) for s in range(start, total, 32 << 20)]
    with open(tmp, "ab") if start else open(tmp, "wb") as f:
        pass
    with cf.ThreadPoolExecutor(16) as ex:
        futs = [ex.submit(fetch_range, url, tmp, s, e) for s, e in ranges]
        for fut in cf.as_completed(futs):
            report(fut.result())
    tmp.rename(dest)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="wheelhouse/")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    jobs = []
    for pkg, ver in PKGS:
        w = pick_wheel(pkg, ver)
        if not w:
            print(f"  no wheel found for {pkg}=={ver}")
            continue
        _, url, fn, size = w
        f = dest / fn
        if f.exists():
            print(f"  exists: {fn} ({size/1e6:.0f} MB)")
            continue
        jobs.append((url, f, size))
        print(f"  queued: {fn} ({size/1e6:.0f} MB)")
    for url, f, size in jobs:
        print(f"downloading {f.name} ...", flush=True)
        dl(url, f)
    print("WHEELHOUSE_DONE")

if __name__ == "__main__":
    main()
