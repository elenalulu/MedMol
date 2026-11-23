# MedMol

**MedMol** is an open-source reproduction of **BoltzMol-1's scoring core**: a target sequence + candidate
small-molecule library in, ranked hit list out — powered by [Boltz-2](https://github.com/jwohlwend/boltz)
(MIT) structure co-folding + affinity prediction.

**What BoltzMol-1 actually is:** Boltz Therapeutics' proprietary model (API-only, closed weights).
Its engine is the same team's open-source **Boltz-2** (MIT, from MIT Jameel Clinic): protein–ligand
co-folding with an affinity head, reported to approach FEP-level ranking accuracy at ~1000× speed.
BoltzMol-1 = Boltz-2 affinity head + massive purchasable-chemistry enumeration + ADME filters.
The closed-source parts (74B synthesis-space enumeration, ADME model suite, active-learning loop)
are **not** reproduced here — this project reproduces the reproducible part: the scoring core.

## Validated on a pre-registered demo (human Carbonic Anhydrase II)

7 molecules (3 known sulfonamide binders + 4 decoys), 5 diffusion samples each, ranked by
`affinity_probability_binary`. [Pre-registered acceptance criteria](docs/DEV_NOTES.md) all passed:

| molecule | bindP | predicted IC50 | literature Ki | known binder |
|---|---|---|---|---|
| ethoxzolamide | 0.999 | 6.7 nM | ~nM (strongest) | ✓ |
| acetazolamide | 0.998 | 18.6 nM | 10–25 nM | ✓ |
| sulfanilamide | 0.977 | 431 nM | ~300 nM | ✓ |
| aspirin | 0.546 | 146 µM | — | decoy |
| glucose | 0.535 | 34 µM | — | decoy |
| caffeine | 0.335 | 33 µM | — | decoy |
| benzene | 0.172 | 183 µM | — | decoy |

Binders and decoys separate cleanly (0.977 vs 0.546 gap). The internal ranking of the three
sulfonamides matches literature potency ordering with sub-log IC50 accuracy. Secondary signal:
ligand iPTM (pose convergence) tracks binder status (≥0.995 for binders, ~0.7 for non-binders) —
usable as a second-stage filter.

## Pipeline

```
targets/*.fasta          target protein sequence(s)
data/*.csv               candidate library (name, smiles, known_binder, note)
scripts/fetch_msa.py     MSA from ColabFold API (form-data protocol, \x00 cleaned) -> .a3m
scripts/build_inputs.py  one Boltz YAML per ligand (structure + affinity property)
scripts/download_weights_parallel.py  16-thread ranged download of the 3 weight files (resumable)
scripts/run_screen.py    batch boltz predict (structure + affinity) on GPU
scripts/rank_results.py  parse affinity/confidence JSONs -> ranked CSV
```

## Quickstart

Requirements: Python 3.12 (boltz pins numpy<2.0; 3.13 has no numpy 1.26 wheel and will fail),
NVIDIA GPU with ≥16 GB VRAM for small complexes (24 GB comfortable), ≥32 GB system RAM
(the affinity head loads a second checkpoint on top of the structure model).

```bash
conda create -y -n boltz2 python=3.12 && conda activate boltz2
pip install boltz          # CN mirrors: pip install -i https://mirrors.aliyun.com/pypi/web/simple boltz

# 1. weights (~6.2 GB: boltz2_conf.ckpt / boltz2_aff.ckpt / mols.tar) into the boltz cache
python scripts/download_weights_parallel.py --dest ~/.cache/boltz/

# 2. MSA + inputs
python scripts/fetch_msa.py --fasta targets/ca2.fasta --out msa/
python scripts/build_inputs.py --target targets/ca2.fasta --library data/demo_library.csv \
    --msa msa/CAH2_HUMAN.a3m --out inputs/

# 3. screen + rank (RTX 4090: ~2-4 min per molecule at 5 diffusion samples)
python scripts/run_screen.py --inputs inputs/ --out results/run1 --samples 5
python scripts/rank_results.py --results results/run1 --library data/demo_library.csv \
    --out results/run1_ranked.csv
```

Air-gapped GPU box: generate Linux wheels on any online machine with
`scripts/download_wheels_gpu.py`, ship them together, then
`pip install --no-index --find-links wheels_gpu/ boltz`. Two-machine (CPU prep + GPU run)
workflow: see [docs/GPU_RUNBOOK.md](docs/GPU_RUNBOOK.md).

## Known limitations

- Affinity head handles ligands ≤128 heavy atoms (boltz 2.2.x); one binder ligand per input.
- Scoring core only — no molecule *generation* (see above).
- **Validated on protein targets only.** The affinity head was trained on protein–ligand data;
  RNA–ligand (and other non-protein) targets are out-of-distribution and unverified here.
- CPU inference works but is impractical for screening (>40 min per complex).
- `msa: empty` degrades accuracy; prefer a precomputed `.a3m` via the `msa:` field.

## Windows-specific pitfalls (all hit and solved, 2026-11)

See [docs/DEV_NOTES.md](docs/DEV_NOTES.md) for the full log: Windows reserved device names inside
`mols.tar` (`AUX/NUL/CON/PRN.pkl`) breaking naive tarfile extraction, `\x00` separators in
ColabFold a3m output, boltz's processed-input cache silently reusing stale MSA settings,
and HF/PyPI rate-limits (hence the parallel downloader and aliyun-mirror instructions).

## Credits & license

- [Boltz-2](https://github.com/jwohlwend/boltz) — MIT. This project is an independent pipeline
  around it; **not affiliated with Boltz Therapeutics or MIT**, and this is not BoltzMol-1.
- MSA via the [ColabFold](https://github.com/sokrypton/ColabFold) public API.
- This repository's own code: MIT (see [LICENSE](LICENSE)).