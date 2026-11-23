"""Download Boltz-2 weights via hf-mirror.com (HuggingFace direct is blocked in the sandbox).
Run on Windows (CPU). Then transfer weights/ to the GPU machine.
Usage: python download_weights.py --dest weights/
"""
import argparse, pathlib, urllib.request, sys, time

BASE = "https://hf-mirror.com/boltz-community/boltz-2/resolve/main/"
FILES = ["boltz2_conf.ckpt", "boltz2_aff.ckpt", "mols.tar"]

def fetch(name: str, dest: pathlib.Path):
    url = BASE + name
    tmp = dest / (name + ".part")
    start = time.time()
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            f.write(chunk); done += len(chunk)
            if total and done % (100 << 20) < (1 << 20):
                print(f"  {name}: {done/1e6:.0f}/{total/1e6:.0f} MB ({done/max(time.time()-start,1)/1e6:.1f} MB/s)", flush=True)
    tmp.rename(dest / name)
    print(f"  saved {dest/name} ({done/1e6:.0f} MB, {time.time()-start:.0f}s)", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="weights/")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        if (dest / f).exists():
            print(f"  exists, skip: {dest/f}")
            continue
        print(f"downloading {f} ...", flush=True)
        fetch(f, dest)
    print("ALL_WEIGHTS_DONE")

if __name__ == "__main__":
    sys.exit(main())
