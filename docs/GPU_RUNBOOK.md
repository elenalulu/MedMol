# GPU_RUNBOOK — Boltz-2 小分子筛选（4090 端）

> 目标：读完本文即可在 GPU 机（Ubuntu 22, vipuser, RTX 4090 Ada）上跑完 7 分子 CA2 demo 筛选，产出排序结果。
> 预计总耗时：环境安装 10-30 min + 筛选 20-40 min。
> 项目来源：Windows 侧已全链路验证到模型推理（结构预测 confidence 0.943 实证），本 runbook 是最后一段。

---

## 0. 拷贝清单（Windows → GPU 机）

**拷贝整个目录** `boltzmol_repro/`（含权重共约 10.5 GB）到 GPU 机任意位置，下文以 `~/boltzmol_repro/` 为例（换了位置就全文替换）：

```
boltzmol_repro/
├── scripts/          # 全部管线脚本
├── targets/ca2.fasta # 人 CA2 (P00918, 260 aa)
├── data/demo_library.csv   # 7 分子库(3 磺酰胺 binder + 4 decoy)
├── msa/CAH2_HUMAN.a3m      # ColabFold MSA, 11,556 行, 已清洗 \x00
├── weights/                # 三件套 6.2 GB: boltz2_conf.ckpt / boltz2_aff.ckpt / mols.tar
└── inputs/*.yaml           # ⚠️ 里面 MSA 是 Windows 路径, 必须在 Step 2 重新生成
```

不需要拷：`wheelhouse/`、`results/`、`README.md`（可留作参考）。

若 GPU 机断网无法 pip 安装，另需在 Windows 侧先跑一步并拷过去（见 Step 1 路线 B）：

```powershell
python scripts/download_wheels_gpu.py --dest wheels_gpu/
```

---

## 1. 环境（conda env: boltz2_312, python 3.12）

```bash
conda create -y -n boltz2_312 python=3.12
conda activate boltz2_312
cd ~/boltzmol_repro
```

**路线 A（GPU 机有网，推荐，走国内镜像）：**

```bash
pip install -i https://mirrors.aliyun.com/pypi/web/simple --retries 8 --timeout 120 boltz
```

**路线 B（离线，用 Windows 侧下好的 wheels）：**

```bash
pip install --no-index --find-links wheels_gpu/ boltz
```

验证（torch 必须看到 CUDA=True）：

```bash
python -c "import torch, boltz; print(torch.__version__, torch.cuda.is_available())"
# 期望: 2.x.x True
```

---

## 2. 权重入缓存 + 重新生成 inputs（两件事都必做）

**2a. 权重**：把三件套放进 boltz 缓存目录（Linux 上 `mols.tar` 会自动解包，无 Windows 保留名问题）：

```bash
mkdir -p ~/.cache/boltz
cp weights/boltz2_conf.ckpt weights/boltz2_aff.ckpt weights/mols.tar ~/.cache/boltz/
```

**2b. 重新生成 YAML**：现有 `inputs/*.yaml` 里的 `msa:` 字段写的是 Windows 绝对路径（`D:/...`），GPU 端直接跑会找不到 MSA。用本地路径重新生成（build_inputs.py 纯标准库，任何机器可跑）：

```bash
python scripts/build_inputs.py \
    --target targets/ca2.fasta \
    --library data/demo_library.csv \
    --msa msa/CAH2_HUMAN.a3m \
    --out inputs/
```

抽查一个确认路径已变为 GPU 机路径：

```bash
grep msa inputs/acetazolamide.yaml
# 期望: msa: "~/boltzmol_repro/msa/CAH2_HUMAN.a3m" 的绝对形式
```

---

## 3. 冒烟测试（1 个分子，先验证全链路再跑全量）

```bash
boltz predict inputs/benzene.yaml \
    --out_dir results/smoke_gpu \
    --accelerator gpu --model boltz2 \
    --recycling_steps 1 --diffusion_samples 1 --sampling_steps 50 \
    --num_workers 0 --override
```

4090 上约 **1-3 分钟**。通过标准：

```bash
ls results/smoke_gpu/boltz_results_benzene/predictions/benzene/
# 期望同时看到: *_model_0.pdb / confidence_*.json / affinity_*.json
```

`affinity_*.json` 存在 = 亲和力头也通了（Windows 侧卡住的就是这一步）。首跑会解包 mols.tar（~2-5 min），属正常。

---

## 4. 全量筛选（7 分子 × 5 samples）

```bash
python scripts/run_screen.py --inputs inputs/ --out results/run1 --samples 5
```

4090 上预计 **20-40 min**（affinity 头每分子 5×200 步采样是大头）。中途断了直接重跑，`--override` 已内置，已完成分子会覆盖。

---

## 5. 排序与验收

```bash
python scripts/rank_results.py --results results/run1 \
    --library data/demo_library.csv --out results/run1_ranked.csv
cat results/run1_ranked.csv
```

**验收标准（预注册口径，跑之前先写死）：**

| 判据 | 期望 |
|---|---|
| 3 个磺酰胺（acetazolamide / sulfanilamide / ethoxzolamide）的 `affinity_probability_binary` | 显著高于 4 个 decoy（caffeine / aspirin / glucose / benzene），排序前 3 占据 |
| acetazolamide `IC50_est_uM` | 与文献 ~10 nM 量级方向一致（不追绝对值，只看相对排序） |
| decoy 侧 | bindP 接近 0 或无显著结合信号 |

通过 = 复现成立（BoltzMol-1 的开源打分核心落地）。磺酰胺内部相对排序不作为判据（Boltz-2 论文口径：排序能力 ~FEP，绝对值有已知 bias）。

---

## 6. 回传（GPU → Windows）

拷回两个东西到 Windows 侧 `boltzmol_repro/results/`：
- `run1_ranked.csv`（判读用）
- `results/run1/` 里的 `predictions/*/affinity_*.json` 与 `confidence_*.json`（留存）

拷回后把 CSV 发我判读。

---

## 7. 排错速查

| 症状 | 根因 | 处置 |
|---|---|---|
| `numpy.core...ArrayMemoryError` / 加载 conf.ckpt 后再加载 aff.ckpt 时挂 | CPU 内存耗尽（Windows 沙箱实证过） | 4090 机正常内存不会触发；若触发，加 swap 或分两次跑（结构一次、affinity 一次） |
| a3m 解析崩 / `invalid literal` 报 NUL | MSA 文件含 `\x00` | 本项目 `msa/CAH2_HUMAN.a3m` **已清洗**；若重新下载 MSA 则需清洗：`python -c "import pathlib; p=pathlib.Path('msa/x.a3m'); p.write_bytes(p.read_bytes().replace(b'\x00', b''))"` |
| 改了 MSA/参数但行为没变 | `--out_dir` 下有 processed 缓存复用旧记录 | 换新 out_dir 或加 `--override` |
| 权重报找不到 | 缓存目录不对 | `export BOLTZ_CACHE=~/.cache/boltz` 后重跑；确认三件套在缓存目录里 |
| torch.cuda.is_available()=False | 装成 CPU torch | 路线 B 的 wheels 若缺 CUDA 版，改在 GPU 机联网用路线 A 重装 |
| fairscale 编译失败（路线 A） | 无编译器 | `sudo apt install g++` 后重试 |
| mols 解包后仍报 CCD 缺失 | 只拷了 mols.tar 没让它解包 | 确认 `~/.cache/boltz/` 下三件套齐全，删掉半成品 `~/.cache/boltz/mols/` 重跑 |
| VRAM OOM（不太可能，260aa+小分子远低于 24GB） | samples 过大 | `--samples 5` 降到 3 |

---

## 附：时间与规模参考

| 阶段 | Windows CPU(实测) | 4090(预期) |
|---|---|---|
| 单分子结构(recycling 1, samples 1, steps 50) | 95 min | 1-3 min |
| 单分子 affinity 头 | OOM 未跑完 | ~2-4 min |
| 全量 7 分子 × 5 samples | 不实用 | 20-40 min |
