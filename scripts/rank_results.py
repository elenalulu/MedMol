"""Parse Boltz-2 affinity outputs and produce a ranked hit list CSV.
Usage:
  python rank_results.py --results results/run1 --library data/demo_library.csv --out results/run1_ranked.csv
"""
import argparse, csv, json, pathlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="boltz --out_dir")
    ap.add_argument("--library", default=None, help="library CSV for notes/known_binder")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    meta = {}
    if a.library:
        with open(a.library, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                meta[row["name"].strip()] = (row.get("known_binder", "").strip(), row.get("note", "").strip())

    root = pathlib.Path(a.results)
    preds = sorted(root.glob("boltz_results_*/predictions/*")) or sorted(root.glob("predictions/*"))
    rows = []
    for d in preds:
        aff = list(d.glob("affinity_*.json"))
        conf = list(d.glob("confidence_*.json"))
        name = d.name
        row = {"name": name}
        if aff:
            j = json.loads(aff[0].read_text())
            row["affinity_probability_binary"] = j.get("affinity_probability_binary")
            row["affinity_pred_value_log10_IC50_uM"] = j.get("affinity_pred_value")
            v = j.get("affinity_pred_value")
            if v is not None:
                row["IC50_est_uM"] = f"{10**v:.4g}"
        if conf:
            j = json.loads(conf[0].read_text())
            row["complex_plddt"] = j.get("complex_plddt")
            row["iptm"] = j.get("iptm")
            row["confidence_score"] = j.get("confidence_score")
        kb, note = meta.get(name, ("", ""))
        row["known_binder"] = kb
        row["note"] = note
        rows.append(row)

    rows.sort(key=lambda r: (-(r.get("affinity_probability_binary") or 0), r.get("affinity_pred_value_log10_IC50_uM") or 0))
    cols = ["name", "affinity_probability_binary", "affinity_pred_value_log10_IC50_uM", "IC50_est_uM",
            "complex_plddt", "iptm", "confidence_score", "known_binder", "note"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"ranked {len(rows)} -> {a.out}")
    for r in rows:
        print(f"  {r['name']:<18} bindP={r.get('affinity_probability_binary')} log10IC50={r.get('affinity_pred_value_log10_IC50_uM')} known={r.get('known_binder') or '?'}")

if __name__ == "__main__":
    main()
