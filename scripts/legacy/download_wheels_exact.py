"""Download EXACT-version cp312 win_amd64 wheels via Aliyun mirror, using the pythonhosted
package path from PyPI JSON (aliyun mirrors the same /packages/ hash-path structure).
Verified: torch-2.15.0 path probe = 3.0 MB/s on aliyun vs ~20KB/s on pythonhosted.
Run: python download_wheels_exact.py --dest wheelhouse/
"""
import argparse, json, pathlib, time, urllib.request

ALIYUN = "https://mirrors.aliyun.com/pypi/web/packages/"
PKGS = [
    ("torch", "2.15.0"),
    ("rdkit", "2026.9.2"),
    ("scipy", "1.13.1"),
    ("pandas", "3.1.1"),
    ("scikit-learn", "1.6.1"),
    ("pillow", None),
]

def get_json(url, retries=4, timeout=20):
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"    api attempt {i+1} failed: {e}", flush=True)
            time.sleep(2 * (i + 1))
    return None

def resolve(pkg, ver):
    api = f"https://pypi.org/pypi/{pkg}/{ver}/json" if ver else f"https://pypi.org/pypi/{pkg}/json"
    d = get_json(api)
    if d is None:
        return None
    ver = d["info"]["version"] if not ver else ver
    for f in d["urls"]:
        fn = f["filename"]
        if fn.endswith(".whl") and "win_amd64" in fn and ("cp312-cp312" in fn or "abi3" in fn):
            return f["url"], fn
    return None

def fetch(url, dest: pathlib.Path):
    path = url.split("/packages/")[1]
    aliyun = ALIYUN + path
    tmp = dest.with_suffix(".part")
    pos = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(aliyun, headers={"Range": f"bytes={pos}-"} if pos else {})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "ab" if pos else "wb") as f:
        cr = r.headers.get("Content-Range", "")
        total = int(cr.split("/")[-1]) if cr else int(r.headers.get("Content-Length", 0))
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done = tmp.stat().st_size
            if done % (16 << 20) < (1 << 20):
                rate = (done - pos) / max(time.time() - t0, 1) / 1e6
                print(f"    {done/1e6:.0f}/{total/1e6:.0f} MB | {rate:.1f} MB/s", flush=True)
    if total and tmp.stat().st_size != total:
        raise RuntimeError(f"incomplete {tmp.stat().st_size}/{total}")
    tmp.rename(dest)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.0f} MB, {time.time()-t0:.0f}s)", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="wheelhouse/")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    for pkg, ver in PKGS:
        r = resolve(pkg, ver)
        if not r:
            print(f"  resolve fail: {pkg}")
            continue
        ph_url, fn = r
        f = dest / fn
        if f.exists():
            print(f"  exists: {fn} ({f.stat().st_size/1e6:.0f} MB)")
            continue
        print(f"downloading {fn} (aliyun) ...", flush=True)
        try:
            fetch(ph_url, f)
        except Exception as e:
            print(f"  FAILED {fn}: {e} (fallback: keep .part for resume)", flush=True)
    print("EXACT_WHEELS_DONE")

if __name__ == "__main__":
    main()
