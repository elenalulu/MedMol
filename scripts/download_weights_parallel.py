"""Parallel multi-range downloader for hf-mirror.com (single stream is ~55 KB/s; N parallel
range streams typically reach several MB/s). Supports resume.
Usage: python download_weights_parallel.py --dest weights/ [--workers 16]
"""
import argparse, pathlib, time, urllib.request, concurrent.futures as cf

BASE = "https://hf-mirror.com/boltz-community/boltz-2/resolve/main/"
FILES = ["boltz2_conf.ckpt", "boltz2_aff.ckpt", "mols.tar"]
CHUNK = 32 * 1024 * 1024  # 32 MB per range request

def head_total(url: str) -> int:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Range", "").split("/")[-1])

def fetch_range(url: str, dest: pathlib.Path, start: int, end: int, retries: int = 6) -> int:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=90) as r, open(dest, "r+b") as f:
                got = 0
                f.seek(start)
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk); got += len(chunk)
                if got == end - start + 1:
                    return got
        except Exception as e:
            print(f"    range {start}-{end} attempt {attempt+1} failed: {e}", flush=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"range {start}-{end} exhausted retries")

def download(url: str, dest: pathlib.Path, workers: int):
    total = head_total(url)
    part = dest.with_suffix(dest.suffix + ".part")
    if part.exists() and part.stat().st_size == total:
        print(f"  already complete: {dest.name}")
        part.rename(dest)
        return
    if not part.exists() or part.stat().st_size != total:
        print(f"  allocating {total/1e9:.2f} GB -> {part.name}", flush=True)
        with open(part, "wb") as f:
            f.truncate(total)
    ranges = [(s, min(s + CHUNK - 1, total - 1)) for s in range(0, total, CHUNK)]
    # skip ranges already fully written: track via marker file listing finished ranges
    done_marker = part.with_suffix(".ranges.done")
    done = set()
    if done_marker.exists():
        done = {int(x) for x in done_marker.read_text().split() if x}
    todo = [r for i, r in enumerate(ranges) if i not in done]
    print(f"  {len(ranges)} chunks, {len(done)} done, {len(todo)} to go", flush=True)
    t0 = time.time(); got_bytes = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_range, url, part, s, e): i for i, (s, e) in enumerate(todo)}
        for n, fut in enumerate(cf.as_completed(futs), 1):
            i = futs[fut]
            got = fut.result()
            done.add(i); got_bytes += got
            if n % 5 == 0 or n == len(todo):
                el = time.time() - t0
                print(f"    {n}/{len(todo)} chunks | {got_bytes/1e6/el:.1f} MB/s | eta {(len(todo)-n)*CHUNK/1e6/max(got_bytes/1e6/el,0.1)/60:.0f} min", flush=True)
                done_marker.write_text(" ".join(str(x) for x in sorted(done)))
    done_marker.write_text(" ".join(str(x) for x in sorted(done)))
    part.rename(dest)
    if done_marker.exists():
        done_marker.rename(done_marker.with_suffix(".done.used"))  # sandbox safe-delete blocks unlink
    print(f"  saved {dest.name} ({total/1e9:.2f} GB, {time.time()-t0:.0f}s)", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="weights/")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--only", default=None, help="download only this file")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        if a.only and f != a.only:
            continue
        if (dest / f).exists():
            print(f"  exists, skip: {f}")
            continue
        print(f"downloading {f} ...", flush=True)
        download(BASE + f, dest / f, a.workers)
    print("ALL_WEIGHTS_DONE")

if __name__ == "__main__":
    main()
