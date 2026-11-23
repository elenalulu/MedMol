"""Download Linux (manylinux, py3.12) wheels for boltz[cuda] on Windows, for offline transfer
to the GPU machine (Ubuntu 22, RTX 4090). Run on Windows (CPU):
  python download_wheels_gpu.py --dest wheels_gpu/
Then transfer wheels_gpu/ to the GPU machine and run:
  pip install --no-index --find-links wheels_gpu/ boltz
"""
import argparse, pathlib, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="wheels_gpu/")
    a = ap.parse_args()
    dest = pathlib.Path(a.dest).resolve(); dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pip", "download",
        "boltz",  # [cuda] extra resolves torch CUDA on linux
        "--dest", str(dest),
        "--platform", "manylinux2014_x86_64",
        "--platform", "manylinux_2_17_x86_64",
        "--python-version", "3.12",
        "--implementation", "cp",
        "--abi", "cp312",
        "--only-binary=:all:",
    ]
    print(" ".join(cmd))
    r = subprocess.run(cmd)
    sys.exit(r.returncode)

if __name__ == "__main__":
    main()
