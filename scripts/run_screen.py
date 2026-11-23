"""Batch-run Boltz-2 predictions (structure + affinity) over a directory of YAML inputs.
Run on GPU machine (4090). CPU works but is very slow.
Usage:
  python run_screen.py --inputs inputs/ --out results/run1 --samples 5
  python run_screen.py --inputs inputs/ --out results/run1 --boltz /path/to/boltz  # custom binary
"""
import argparse, pathlib, subprocess, sys, shutil

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=5, help="diffusion_samples per complex")
    ap.add_argument("--recycling", type=int, default=3)
    ap.add_argument("--boltz", default=None, help="path to boltz binary (default: on PATH)")
    ap.add_argument("--accelerator", default="gpu", choices=["gpu", "cpu"])
    ap.add_argument("--model", default="boltz2")
    ap.add_argument("--max_msa", type=int, default=None, help="cap MSA seqs (e.g. 64 for CPU-lowRAM)")
    ap.add_argument("--extra", nargs="*", default=[], help="extra flags passed to boltz predict")
    a = ap.parse_args()

    boltz = a.boltz or shutil.which("boltz") or "boltz"
    inputs = sorted(pathlib.Path(a.inputs).glob("*.yaml"))
    if not inputs:
        sys.exit(f"no yaml inputs in {a.inputs}")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    print(f"screening {len(inputs)} complexes -> {out}")

    ok, fail = [], []
    for i, yml in enumerate(inputs, 1):
        cmd = [
            boltz, "predict", str(yml),
            "--out_dir", str(out),
            "--recycling_steps", str(a.recycling),
            "--diffusion_samples", str(a.samples),
            "--output_format", "pdb",
            "--accelerator", a.accelerator,
            "--model", a.model,
            *(["--max_msa_seqs", str(a.max_msa), "--num_subsampled_msa", str(a.max_msa)] if a.max_msa else []),
            *a.extra,
        ]
        print(f"[{i}/{len(inputs)}] {yml.stem}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd)
        (ok if r.returncode == 0 else fail).append(yml.stem)
    print(f"\nDONE ok={len(ok)} fail={len(fail)}")
    if fail:
        print("failed:", ", ".join(fail))

if __name__ == "__main__":
    main()
