"""Build one Boltz-2 YAML input per ligand from a target FASTA + ligand library CSV.
Run on Windows (CPU) or GPU machine.
Usage:
  python build_inputs.py --target targets/ca2.fasta --library data/demo_library.csv \
      --msa msa/ca2.a3m --out inputs/
"""
import argparse, csv, pathlib

YAML_TPL = """version: 1
sequences:
  - protein:
      id: A
      sequence: "{seq}"
{msa_line}  - ligand:
      id: L
      smiles: "{smiles}"
properties:
  - affinity:
      binder: L
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="target FASTA (first record)")
    ap.add_argument("--library", required=True, help="CSV: name,smiles,known_binder,note")
    ap.add_argument("--msa", default=None, help="precomputed .a3m path (optional)")
    ap.add_argument("--out", default="inputs/")
    a = ap.parse_args()

    seq, started = [], False
    for line in pathlib.Path(a.target).read_text().splitlines():
        if line.startswith(">"):
            if started: break
            started = True
        else:
            seq.append(line.replace(" ", ""))
    seq = "".join(seq)
    print(f"target: {len(seq)} aa")

    msa_path = pathlib.Path(a.msa).resolve() if a.msa else None
    if msa_path and not msa_path.exists():
        raise SystemExit(f"MSA file not found: {msa_path}")
    msa_line = f"      msa: \"{msa_path.as_posix()}\"\n" if msa_path else ""

    outdir = pathlib.Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(a.library, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name, smi = row["name"].strip(), row["smiles"].strip()
            yml = YAML_TPL.format(seq=seq, msa_line=msa_line, smiles=smi)
            p = outdir / f"{name}.yaml"
            p.write_text(yml, encoding="utf-8")
            n += 1
            print(f"  wrote {p}")
    print(f"done: {n} inputs in {outdir}/")

if __name__ == "__main__":
    main()
