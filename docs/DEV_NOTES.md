# BoltzMol-1 复现:基于开源 Boltz-2 的小分子 hit discovery 管线

## 背景

微信文章提到的是 Boltz Therapeutics 2026-06 发布的**专有模型 BoltzMol-1**(仅 API,闭源权重)。
但其核心引擎就是同一团队(MIT Jameel Clinic)开源的 **Boltz-2**(MIT license,代码/权重全开,
github.com/jwohlwend/boltz):蛋白-小分子共折叠 + 亲和力预测头,官方口径
"affinity 精度接近 FEP、快 1000x"。BoltzMol-1 = Boltz-2 亲和力头 + 大规模可购买/可合成化学空间搜索
+ ADME 过滤的生产级封装。

本项目复现其**核心科学能力**:target 序列 + 候选小分子库 → Boltz-2 共折叠打分 → 亲和力排序 → hit 列表。

## 管线结构

```
targets/ca2.fasta        目标蛋白(FASTA,可加多个靶点)
data/demo_library.csv    候选分子库(SMILES + 备注 + 已知活性标注)
scripts/fetch_msa.py     [Windows/CPU] 向 ColabFold API 要 MSA,存 .a3m(离线传输用)
scripts/build_inputs.py  [Windows/CPU] 生成每个 ligand 一个的 Boltz YAML(含 affinity property)
scripts/download_weights.py  [Windows/CPU] 经 hf-mirror 下载 boltz-2 权重(HF 直连被墙)
scripts/run_screen.py    [GPU/4090] 批量跑 boltz predict
scripts/rank_results.py  解析 affinity_complex.json,产出排序 CSV
```

## 预期判读(demo:人碳酸酐酶 II)

- acetazolamide / sulfanilamide(磺酰胺类,已知 CA2 结合剂)应排在 caffeine / glucose / aspirin 等 decoy 前
- 排序指标 = `affinity_probability_binary`(hit discovery 阶段官方推荐指标);
  `affinity_pred_value` = log10(IC50 µM),越低越强,换算 µM = 10^value

## 用法

```bash
# Windows 本机(CPU)
python scripts/fetch_msa.py --fasta targets/ca2.fasta --out msa/
python scripts/build_inputs.py --target targets/ca2.fasta --library data/demo_library.csv --msa msa/ca2.a3m --out inputs/
python scripts/download_weights_parallel.py --dest weights/   # 16线程并行+断点续传,单线程版太慢

# 4090 GPU 机(Ubuntu, 权重与 inputs 目录整个 rsync 过去)
python scripts/run_screen.py --inputs inputs/ --out results/run1 --samples 5
python scripts/rank_results.py --results results/run1 --library data/demo_library.csv --out results/run1_ranked.csv
```

## 已知边界

- Boltz-2 affinity ligand ≤128 原子(v2.2.x);affinity 一次只能指定一个 binder ligand
- `msa: empty` 是精度损失不是显存优化;离线时用预计算 .a3m 走 `msa:` 字段
- CPU 推理可用但极慢,生产筛选必须在 GPU 上跑
- 这复现的是 BoltzMol-1 的**打分核心**;其 74B 可合成空间枚举、ADME 模型组、活性学习闭环不在开源范围

## 环境坑(实测,2026-11-21)

- **Python 必须 3.12**(boltz 锁 numpy<2.0,numpy 1.26 无 cp313 wheel,py3.13 会拉 sdist 源码编译必挂)。
  本机 venv:`D:\WorkBuddy\home\binaries\python\envs\boltz2_312`(anaconda 3.12.4 建)。
- **ColabFold API 是 form-data 不是 JSON**:POST `https://api.colabfold.com/ticket/msa`,
  body=`q=>101\n<SEQ>\n` + `mode=env`,轮询 `/ticket/<id>` 到 COMPLETE,`/result/download/<id>` 下 tar.gz 取 uniref.a3m。
- **HuggingFace 直连被墙**,权重走 `https://hf-mirror.com`(scripts/download_weights.py 已内置);
  需要 3 个文件:boltz2_conf.ckpt / boltz2_aff.ckpt / mols.tar。
- ColabFold 实测:CA2(260 aa)~100s 返回 11,556 行 a3m。

## Windows 本机冒烟测试记录(2026-11-21,全链路已验证)

- 环境:venv `boltz2_312`(anaconda 3.12.4),`pip install -i https://mirrors.aliyun.com/pypi/web/simple boltz`
  (pythonhosted 单流被限到 ~20KB/s,阿里云镜像 3-5 MB/s;aliyun 的 simple 索引旧版排前面,**不要手工挑版本**,交给 pip 解析)
- 权重缓存:`BOLTZ_CACHE=D:/WorkBuddy/alphafold-web/boltzmol_repro/weights`,boltz 首跑自动找
  boltz2_conf.ckpt / boltz2_aff.ckpt / mols.tar(源码 main.py: cache/ 下平铺)
- **mols.tar 解包大坑**:tar 含 `mols/AUX.pkl`、`NUL.pkl`、`CON.pkl`、`PRN.pkl` 等 Windows 保留设备名文件,
  tarfile 解包直接 FileNotFoundError。 workaround=逐成员提取,保留名跳过(4 个非标准 CCD 组件,不影响常规筛选);
  其余 45,223 个 pkl 全部解出。**注意手动 mkdir mols/ 空目录会让 boltz 跳过解包导致 CCD not found**
- **ColabFold a3m 含 \x00 分隔符**,bola parse_a3m 会 KeyError,下载后需 `replace(b'\x00', b'')`
- CPU 推理实测:260 aa 蛋白 + 配体,默认 MSA(1024 sub)在沙箱内 OOM(786MB 单次分配);
  `--max_msa_seqs 64 --num_subsampled_msa 64` 可过,**且换 MSA 参数必须换新 out_dir**(processed 缓存会复用旧记录)
- CPU 单复合物耗时 >40min(还没算 affinity 的 5×200 步),**demo 筛选务必在 4090 上跑**
