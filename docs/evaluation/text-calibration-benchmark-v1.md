# 文本校准评测标准 v1

本轮先固定“音频说了什么”和“怎样计算差异”，不修改校准模型、提示词或应用门槛。评测对象是当前英文文本校准功能。

## 参考答案与来源

采用 [Google FLEURS `en_us`](https://huggingface.co/datasets/google/fleurs)，固定提交 `70bb2e84b976b7e960aa89f1c648e09c59f894dd`。发布方记录了额外工作人员对录音与输入句子的一致性检查，不合格录音被丢弃；这是选择该数据的主要依据。[原论文 §2.1](https://arxiv.org/pdf/2205.12446)

- 证据状态：`publisher_human_validated`，发布方人工验证。
- 本项目复听状态：`pending`。没有把下载、跑 ASR 或模型之间一致当成人工听音确认。
- 参考内容保留 `raw_transcription` 和发布方 `transcription` 两列。评分从原始参考文本开始，双方统一使用下述规则。
- 每份录音保留来源文件名、句子 ID、源分区、样本数、采样率、SHA-256；参考 TXT、辅助 SRT 也有校验和。
- SRT 是 `0 → 整段音频时长` 的单条字幕，便于播放核对，**不是人工标注的句子/词级时间轴**。本轮不测时间对齐准确率。
- 数据许可为 CC BY 4.0；保留 FLEURS 作者、论文和数据源署名。更完整的来源核查见 [研究记录](benchmark-source-research.md)。

第一版的固定清单位于 `tests/evaluation/calibration/reference-v1/manifest.json`。

## 抽样与分区

首批 48 份录音，对应 48 个不同句子：

| 本项目分区 | FLEURS 来源 | 数量 | 用途 |
| --- | --- | ---: | --- |
| `dev` | `validation` | 24 | 验证流程、观察错误、未来调参 |
| `heldout` | `validation` 的另一组句子 | 24 | 本项目内部保留集，冻结策略之后再评测 |

选择规则不使用任何模型输出：按 `SHA256("echoalign-reference-v1:" + sentence_id + ":" + recording_filename)` 排序；每个句子只取首个符合条件的录音，前 24 个用于 `dev`，接下来的 24 个用于 `heldout`。音频长 5–30 秒，原始文本含 10–70 个空格分隔词；首版排除含数字、全大写缩写和带点首字母缩写的句子，减少词面评测中的书写形式歧义。该限制是 pilot 的覆盖边界，不能将结果外推到数字、缩写或整个 FLEURS。

这里的 `heldout` 是从官方 `validation` 划出的内部保留样本，**不是 FLEURS 官方 test**。首版构建时官方 test 的数据服务持续返回错误，所以未使用该分区；内部划分仍按相同固定哈希规则进行，开发集原有 24 个样本保持不变。官方 test 留待后续扩大评测。

在两个分区之间检查句子 ID、录音 ID、参考文本重复。FLEURS 没有为本工具提供说话人唯一键，因此这里不宣称已经独立验证说话人隔离。公开数据及文本可能已进入底层模型的预训练；污染状态记录为 `unknown`。

每个片段独立处理。不把互不相关的句子拼接成“前三句上下文”。因此首版能检验单片段内的纠错与误改，不能完整评价跨片段长上下文、访谈口语或歌曲。

## 评分规则：`english-lexical-v1`

1. 参考与输出都做 Unicode NFKC、大小写折叠，统一弯撇号。
2. 按字母/数字词切分，忽略大小写、标点、空白和换行；连字符分词，保留词内部撇号，例如 `don't`。
3. 保留重复词、语气词、词序、时态、单复数和实际增删；不能用“更通顺”替代对录音的忠实程度。
4. 不自动展开缩写、数字或缩约词，不采用同义词替换，也不使用 LLM 判断答案。
5. 候选输出出现数字或缩写时，标记 `normalization_review_required`。严格词面 WER 仍可复现，但这种差异需要复核，不能直接当作语义纠错收益。例如 `two` 和 `2` 在 v1 下不同。

主指标是词错误率：`WER = (替换数 + 删除数 + 插入数) / 参考词数`。每个片段分别计算最短编辑距离，再汇总错误数和参考词数；不把所有音频首尾拼接评分，也不对长短不同片段的 WER 做简单平均。WER 可以超过 100%，不能把 `1-WER` 简化宣传为“文字正确率”。

参考使用整段文字，评分使用 JSON 的 `segments[].text`；不要求 ASR 字幕分段与参考 SRT 分段一致，也不使用保留原文的 `tokens[].text` 给校准结果评分。

## 原始 ASR 与校准的对照

先保存一份原始 ASR JSON。未来所有校准候选从这份 JSON 的独立副本开始，禁止每次重跑 ASR 后把差异全部归因于校准。参考答案只进入评测器，不进入 ASR 热词、提示词或校准上下文；上下文仍按实际产品逻辑来自识别结果。

评分工具报告：

| 指标 | 含义 |
| --- | --- |
| 原始 WER、校准 WER | 对同一固定参考的词面错误率 |
| 净减少错误数、WER 降低百分点 | 校准后总错误是否更少 |
| 改善 / 恶化 / 持平片段数 | 避免整体平均掩盖局部退步 |
| 修改但 WER 持平的片段 | 可能修好一处、又改坏另一处，需要逐项检查 |
| 原本零错误的片段被改坏数及比例 | 直接观测误改；分母为零时报告 `null` |
| 需归一化复核片段数 | 提醒区分书写形式和真实词错误 |

这些指标不等于“校准建议准确率”：一条建议可能修改多个词，同一片段也可能同时有改善和损害。建议级 precision/recall 要在明确的人工错误区间标注之后再计算，不能从本报告推导。

缺少任何应评测输出、参考文件被改动、基线已包含校准结果、原始来源不匹配，都会报错；不会只统计成功样本。候选还必须保留原始 token、字幕 ID、时间戳及 `original_text`，保证对照可追溯。

## 复核与准入

第一版是验证流程和发现问题的 pilot，不设置可自动通过的发布门槛。此前合成集的 95% 修改准确率、70% 召回率、2% 误改率不能直接套到这 48 个片段上。

进入模型调优前，先对开发集基线的差异做音频复核。需要修改参考时，保存原文、修订、音频区间、复核理由和复核者；形成新的参考版本。不得仅因模型输出“看起来合理”而修改标准答案。疑点未解决的片段应明确标记，不能悄悄删除来改善分数。

未来候选至少应降低固定开发集 WER，逐项检查新增误改，再使用冻结的保留集验证；保留集一旦用于选模型或改提示词，应转为开发数据，另准备未使用过的测试集。小样本结果始终同时报告分子与分母。要决定是否默认启用，还需要扩大样本，并加入真实使用场景与连续语音。

歌曲可在下一版作为独立分组加入：用匹配录音版本、经听音核对的歌词，保留实际重复和即兴演唱；不与朗读语料混算一个总分。

## 可复现命令

下列命令在项目根目录执行。工具仅使用 Python 标准库、`curl` 和现有的 `ffprobe`；评分不会加载任何模型。

```bash
# 检查已经准备好的音频、参考文本、SRT 和校验和
.venv/bin/python tools/prepare_reference_benchmark.py verify

# 在另一台机器恢复未提交 Git 的音频，保持 manifest 和参考答案不变
.venv/bin/python tools/prepare_reference_benchmark.py restore

# 生成未启用校准的开发集基线；不要把参考 TXT/SRT 传给识别器
.venv/bin/easr tests/evaluation/calibration/reference-v1/audio/dev \
  --output-dir tests/evaluation/calibration/reference-v1/runs/raw-asr/dev

# 只评原始 ASR
.venv/bin/python tools/score_reference_benchmark.py \
  tests/evaluation/calibration/reference-v1/manifest.json \
  tests/evaluation/calibration/reference-v1/runs/raw-asr/dev \
  --output tests/evaluation/calibration/reference-v1/runs/raw-asr/dev.metrics.json

# 用现有固定模型处理保存的 ASR；该工具不读取参考文本，也不重跑 ASR
HF_HUB_OFFLINE=1 PYTHONPATH=src .venv/bin/python tools/run_reference_calibration.py \
  tests/evaluation/calibration/reference-v1/runs/raw-asr/dev \
  PATH_TO_NEW_CALIBRATION_OUTPUT_DIRECTORY

# 将来对从相同基线生成的候选结果做比较
.venv/bin/python tools/score_reference_benchmark.py \
  tests/evaluation/calibration/reference-v1/manifest.json \
  tests/evaluation/calibration/reference-v1/runs/raw-asr/dev \
  --candidate-dir PATH_TO_CALIBRATED_JSON_DIRECTORY \
  --output PATH_TO_COMPARISON_REPORT.json
```

首次构建使用 `prepare_reference_benchmark.py build`；已存在 manifest 时拒绝覆盖。新抽样必须使用新的输出目录。`--partition heldout` 需要明确指定，默认只评分开发集。

`run_reference_calibration.py` 需要现有 MLX 依赖及固定模型缓存，输出目录必须是新目录。它保存逐文件校准审计、计数、耗时、基线校验和、模型及代码版本；有任何失败时返回非零退出码。评分仍是后续独立步骤。
