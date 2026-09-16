# 英文文本校准参考集 v1

已准备 **48 条音频、48 份参考 TXT、48 份辅助 SRT**，总长 **7 分 44.92 秒**。来源为 Google FLEURS 英文验证集，发布方对录音与输入句子做过人工一致性验证；本项目尚未逐条复听。

- 开发集：24 个不同句子，4 分 1.80 秒，已保存关闭校准的 ASR 基线。
- 内部保留集：另外 24 个不同句子，3 分 43.12 秒，未运行 ASR 或校准。它是官方 validation 的内部划分，不是官方 test。
- SRT 每段只有一条 `0 → 录音结束` 字幕，用于核对文字，不是时间对齐标准。
- 已按现有方案运行开发集校准，模型、提示词与门槛均未调整；内部保留集未使用。

[完整评测标准](../../../../docs/evaluation/text-calibration-benchmark-v1.md) · [来源核查](../../../../docs/evaluation/benchmark-source-research.md) · [固定清单和校验和](manifest.json)

## 开发集基线

严格词面 WER 为 **2.71%（14 / 517）**：9 个替换、2 个删除、3 个插入。24 条中，16 条在固定归一化规则下与参考一致，8 条有差异。1 条包含数字书写形式差异，需单独复核；这些数字不能直接宣传为语义正确率。

[基线报告](runs/raw-asr/dev.metrics.json) · [运行版本与参数](runs/raw-asr/run.json) · [逐条差异复核入口](review.md)

## 现有校准方案结果

开发集 24 个片段、40 个校准单元全部完成，但 **0 条建议被应用**。校准前后 WER 均为 **2.71%（14 / 517）**，没有修复错误，也没有新增误改。修改准确率的分母为 0，应报告“无法计算”，不能报告为 100%。校准耗时约 4 分 37 秒。

[详细评测报告](runs/policy-1-qwen3.5-4b-4bit/REPORT.md) · [前后对比指标](runs/policy-1-qwen3.5-4b-4bit/dev.metrics.json)

## 文件组织

- `audio/dev/`、`audio/heldout/`：源录音的固定音频副本，已在本机下载。约 29.8 MB，不加入 Git；可用恢复命令按校验和重新下载。
- `references/dev/`、`references/heldout/`：参考 TXT 和辅助 SRT。
- `manifest.json`：固定样本、官方 raw/normalized 文本、分区、源版本、校验和及复核状态。
- `runs/raw-asr/dev/`：原始 ASR JSON、SRT、VTT 和运行指标；未来候选必须从这些 JSON 的副本开始。

## 核验与恢复

在项目根目录执行：

```bash
.venv/bin/python tools/prepare_reference_benchmark.py verify
.venv/bin/python tools/prepare_reference_benchmark.py restore
```

评分命令和防止参考答案泄露的约定见[完整标准](../../../../docs/evaluation/text-calibration-benchmark-v1.md)。已有 manifest 拒绝覆盖；调整答案或抽样规则应建立新版本。

## 来源署名

FLEURS — Alexis Conneau, Min Ma, Simran Khanuja, Yu Zhang, Vera Axelrod, Siddharth Dalmia, Jason Riesa, Clara Rivera, Ankur Bapna (2022).

[论文](https://arxiv.org/abs/2205.12446) · [官方数据](https://huggingface.co/datasets/google/fleurs) · [固定版本](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

本项目仅抽样并生成 TXT/SRT 容器，参考句子未重写。公开语料是否进入底层模型预训练尚未核查；这是建立评测流程的小样本，不是发布准入证明。
