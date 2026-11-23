"""Fetch MSA (.a3m) for target proteins via ColabFold API (form-data protocol, same as boltz).
Run on Windows (CPU, has internet). Saves uniref30 MSA as .a3m for offline transfer.
Usage: python fetch_msa.py --fasta targets/ca2.fasta --out msa/
"""
import argparse, io, json, pathlib, random, tarfile, time, urllib.parse, urllib.request

HOST = "https://api.colabfold.com"

def http_post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "boltz",
        "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "boltz"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def run(query: str, mode: str = "env") -> str:
    out = http_post(f"{HOST}/ticket/msa", {"q": query, "mode": mode})
    while out.get("status") in ("UNKNOWN", "RATELIMIT"):
        time.sleep(5 + random.randint(0, 5))
        out = http_post(f"{HOST}/ticket/msa", {"q": query, "mode": mode})
    if out.get("status") == "ERROR":
        raise RuntimeError("MMseqs2 API error: check sequence validity / try later")
    if out.get("status") == "MAINTENANCE":
        raise RuntimeError("MMseqs2 API under maintenance")
    jid = out["id"]
    print(f"  job {jid} status={out.get('status')}")
    while out.get("status") in ("UNKNOWN", "RUNNING", "PENDING"):
        time.sleep(5 + random.randint(0, 5))
        out = http_get_json(f"{HOST}/ticket/{jid}")
        print(f"  status={out.get('status')}", flush=True)
    if out.get("status") != "COMPLETE":
        raise RuntimeError(f"job ended with status {out.get('status')}")
    req = urllib.request.Request(f"{HOST}/result/download/{jid}", headers={"User-Agent": "boltz"})
    with urllib.request.urlopen(req, timeout=600) as r:
        tar_bytes = r.read()
    print(f"  downloaded tar.gz ({len(tar_bytes)/1e6:.1f} MB)")
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        a3m = tar.extractfile("uniref.a3m").read().decode()
    a3m = a3m.replace("\x00", "")  # ColabFold inserts NUL separators; boltz parse_a3m chokes on them
    return a3m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fasta", required=True)
    ap.add_argument("--out", default="msa/")
    a = ap.parse_args()
    outdir = pathlib.Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    seq, name, started = [], "target", False
    for line in pathlib.Path(a.fasta).read_text().splitlines():
        if line.startswith(">"):
            if started: break
            name, started = line[1:].split("|")[0], True
        else:
            seq.append(line.replace(" ", ""))
    seq = "".join(seq)
    print(f"[{name}] len={len(seq)} -> ColabFold MSA search...")
    query = f">101\n{seq}\n"
    a3m = run(query)
    p = outdir / f"{name}.a3m"
    p.write_text(a3m)
    print(f"saved {p} ({a3m.count(chr(10))} lines)")

if __name__ == "__main__":
    main()
