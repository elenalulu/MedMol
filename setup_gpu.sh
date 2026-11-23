#!/usr/bin/env bash
# GPU 机(ubuntu22, 4090)上的安装与筛选脚本
# 前置:从 Windows 拷贝过来 boltzmol_repro/ 整个目录(含 inputs/, msa/, weights/, wheels_gpu/ 或直接联网装)
set -e

ENV=boltz2_312
conda create -y -n $ENV python=3.12 2>/dev/null || true
conda activate $ENV

# 方式 A:GPU 机有网时直接装
pip install boltz
# 方式 B:离线时用 Windows 侧下载好的 linux wheels
# pip install --no-index --find-links wheels_gpu/ boltz

# 权重放缓存目录(boltz 首跑会自动找,也可手动放)
mkdir -p ~/.cache/boltz
cp weights/boltz2_conf.ckpt weights/boltz2_aff.ckpt weights/mols.tar ~/.cache/boltz/ 2>/dev/null || true

# 跑筛选(7 个 CA2 demo 分子,结构+亲和力)
python scripts/run_screen.py --inputs inputs/ --out results/run1 --samples 5
# 汇总排序
python scripts/rank_results.py --results results/run1 --library data/demo_library.csv --out results/run1_ranked.csv
echo "done -> results/run1_ranked.csv"
