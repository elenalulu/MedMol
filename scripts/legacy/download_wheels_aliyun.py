"""Download big wheels from Aliyun PyPI mirror (~3 MB/s single stream vs pythonhosted throttled).
Run: python download_wheels_aliyun.py --dest wheelhouse/
"""
import argparse, pathlib, re, time, urllib.request

MIRROR = "https://mirrors.aliyun.com/pypi/web/simple/"
PKGS = [
    ("torch", "2.15.0"),
    ("rdkit", "2026.9.2"),
    ("scipy", "1.13.1"),
    ("pandas", "3.1.1"),
    ("scikit-learn", "1.6.1"),
    ("pillow", None),
]
WANT = "cp312-cp312-win_amd64"

def get_index(pkg):
    with urllib.request.urlopen(MIRROR + pkg + "/", timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def pick_url(body):
    for m in re.finditer(r'href="([^"]+)"', body):
        href = m.group(1).split("#")[0]
        if WANT in href:
            url = urllib.request.urljoin(MIRROR + "torch/", href)
            return url
    return None

def fetch(url, dest: pathlib.Path):
    tmp = dest.with_suffix(".part")
    pos = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={pos}-"} if pos else {})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "ab" if pos else "wb") as f:
        total = r.headers.get("Content-Range", "").split("/")[-1] if pos else r.headers.get("Content-Length")
        total = int(total) if total else 0
        mode = f"resume@{pos/1e6:.0f}MB" if pos else "full"
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done = tmp.stat().st_size
            if done % (16 << 20) < (1 << 20):
                rate = (done - pos) / max(time.time() - t0, 1) / 1e6
                eta = (total - done) / 1e6 / max(rate, 0.1)
                print(f"    {done/1e6:.0f}/{total/1e6:.0f} MB | {rate:.1f} MB/s | eta {eta:.0f}s", flush=True)
    if total and tmp.stat().st_size != total:
        raise RuntimeError(f"incomplete: {tmp.stat().st_size}/{total}")
    tmp.rename(dest)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.0f} MB, {time.time()-t0:.0f}s)", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="wheelhouse/")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    for pkg, ver in PKGS:
        fn_pat = ver or ""
        try:
            body = get_index(pkg)
        except Exception as e:
            print(f"  index fail {pkg}: {e}")
            continue
        url = pick_url(body)
        if not url:
            print(f"  no {WANT} wheel for {pkg}")
            continue
        name = url.rsplit("/", 1)[-1]
        f = dest / name
        if f.exists():
            print(f"  exists: {name}")
            continue
        print(f"downloading {name} ...", flush=True)
        fetch(url, f)
    print("ALIYUN_WHEELS_DONE")

if __name__ == "__main__":
    main()
