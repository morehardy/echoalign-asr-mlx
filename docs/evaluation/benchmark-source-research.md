# 文本校准基准：音频与参考文本来源核查

核查日期：2026-09-16。建议先用 **Google FLEURS 的 `en_us` 建立逐片段的文字评测 pilot**，保留歌曲作为单独的后续测试。这里区分“发布方验证过录音与文本一致”和“本项目已独立听音复核”；本次仅完成来源核查，未听音，也未运行模型质量评测。

| 来源 | 已核实的参考质量 | 对本项目的用途 |
| --- | --- | --- |
| FLEURS `en_us` | 每段朗读由其他工作人员检查与输入句子是否一致，不合格录音被丢弃 | 首批公开参考样本；标签可用 `publisher_human_validated` |
| LibriSpeech dev/test | 书本文本经自动对齐、筛选；未查到逐条人工听音修订的明确承诺 | 可复现的补充基准；标签用 `published_reference` |
| GigaSpeech dev/test | 明确由专业人工转写员处理 | 后续口语、播客扩展；访问有申请条件 |
| Jam-ALT 英文子集 | 歌词经规范修订，现有行级时间经过人工纠正 | 独立歌曲测试，不能与一般朗读结果混算 |

以上分别依据 [FLEURS 原论文 §2.1](https://arxiv.org/pdf/2205.12446)、[LibriSpeech 原论文 §2](https://www.danielpovey.com/files/2015_icassp_librispeech.pdf)、[GigaSpeech 官方说明](https://github.com/SpeechColab/GigaSpeech#transcribed-evaluation-subsets)、[Jam-ALT 数据卡](https://huggingface.co/datasets/jamendolyrics/jam-alt/blob/main/README.md)。

FLEURS 的来源与边界：

- 官方入口为 [`google/fleurs`](https://huggingface.co/datasets/google/fleurs)，许可标为 **CC BY 4.0**；有音频、`raw_transcription`、`transcription`、句子 `id` 和音频路径。本次核对的仓库提交为 [`70bb2e84b976b7e960aa89f1c648e09c59f894dd`](https://huggingface.co/datasets/google/fleurs/commit/70bb2e84b976b7e960aa89f1c648e09c59f894dd)，英文文件在 [`parquet-data/en_us`](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd/parquet-data/en_us)。下载时记录这个提交、文件校验和、抽样规则及所选音频文件名，不能只记录会移动的 `main`。旧加载器的 `2.0.0` 是实现中的版本标记，不足以替代文件级版本记录。
- 原论文描述 Wikipedia/FLoRes 句子的母语朗读及独立工作人员的一致性检查；它是人工验证的朗读语料，并不保证每个参考都无误。同一句可有多份录音，句子 `id` 不能独自充当录音唯一键。第一批每个句子只取一份录音，避免重复文本放大样本量；不把互不相关的片段拼接成上下文。[FLEURS 论文 §2](https://arxiv.org/pdf/2205.12446)
- 保留原始与官方归一化文本。论文列出 NFC、FST、大小写及标点处理，但 **不能假定数字已转成口述词形**：英文开发集的归一化列仍保留数字、千位分隔符和部分连字符；例如句子 `1609` 的 `70` 仍是数字。应预先定义数字、缩写、撇号与连字符的评分规则，并在报告中区分书写形式差异与实际词错误。[官方英文 dev.tsv](https://huggingface.co/datasets/google/fleurs/blob/70bb2e84b976b7e960aa89f1c648e09c59f894dd/data/en_us/dev.tsv)
- 数据卡提供的是片段文本，没有人工逐词或逐句字幕时间字段。因此从 `0` 到片段总时长生成的 SRT 只能辅助复听，必须标注为片段边界；不得用于证明时间对齐准确率。朗读结果也不能直接代表会议、访谈或噪声环境。[FLEURS 数据结构及限制](https://huggingface.co/datasets/google/fleurs#dataset-structure)

LibriSpeech 的适用范围：

[OpenSLR SLR12](https://www.openslr.org/12/) 提供约 1000 小时、16 kHz 英文有声书朗读、明确的 dev/test 分区及 CC BY 4.0 许可。论文 §2 描述先将书本文字大写化、去标点并展开部分缩写，再对齐和筛除不匹配音频；dev/test 在断句上采用了不同规则。**自动筛选、说话人检查不等于逐条人工纠字**；[官方 Hugging Face 数据卡](https://huggingface.co/datasets/openslr/librispeech_asr/blob/main/README.md) 的 annotation process 仍缺详细说明。因此原始参考可测归一化词错误率，不能据此评价标点、大小写或人工字幕时间轴；也不能把它标成本项目已听音确认的金标准。[原论文 §2–3](https://www.danielpovey.com/files/2015_icassp_librispeech.pdf)

歌曲与口语的后续扩展：

[Jam-ALT](https://audioshake.github.io/jam-alt/) 共用 JamendoLyrics 的音频，专门规范拼写、背景人声、非词声音、大小写、标点和换行；公开示例固定版本为 `v1.4.0`。当前版本已有行级时间，但没有词级时间。歌曲可以检验拖音、伴奏、重复副歌下的纠错，但评价必须对应同一录音版本，不能仅拿网上歌词当答案；只取英文子集，并单独汇报。歌曲许可需保存每曲来源信息，不能把所有音频一概写成统一的 CC BY 4.0。[数据卡及贡献说明](https://huggingface.co/datasets/jamendolyrics/jam-alt/blob/main/README.md)、[原始数据的逐曲 `license_type`](https://huggingface.co/datasets/jamendolyrics/jamendolyrics)

[GigaSpeech](https://github.com/SpeechColab/GigaSpeech) dev/test 的人工转写证据更明确，也包含播客和 YouTube 场景；但 [官方 HF 页面](https://huggingface.co/datasets/speechcolab/gigaspeech) 要求申请访问、同意联系方式共享及非商业研究/教育等条件。页面顶部的 Apache-2.0 标签不能代替其音频访问条款，因此本轮先选无需这一步的 FLEURS。

建议本项目采用的证据口径：

1. 从 `validation` 按固定规则选小样本，称为“公开语料 pilot”；保留官方 `test` 作后续冻结测试。按句子去重并检查分区间重叠，不能把相同句子的不同录音分别用于调参与最终报告。
2. 为每条样本分别保存来源证据与本地复核状态。初始状态应是“发布方已人工验证；本项目复听待完成”。复核有疑点时保留原文、修订、理由和审核记录，版本化参考集；不能根据某个模型输出直接改答案。
3. 原始 ASR 和校准 ASR 对照同一份固定参考；参考文本只进入评测器，不进入 ASR 提示、热词或校准上下文。按片段计算编辑距离再汇总 WER，保留改善、恶化、原本正确被改错的样本。单靠“修改了多少”不能说明收益。
4. FLEURS、LibriSpeech 都是公开语料，源文本又长期公开；**本项目未使用测试集调参，不等于底层模型预训练未见过文本或音频**。本轮未审计任何 ASR/LLM 训练清单，污染状态只能记为 `unknown`。这是评测设计上的限制，不是已证明当前模型存在污染。小样本结果用于验证流程和发现错误，不能称“通用文本正确率已被证明提高”；最终还需独立听音核对、未参与调参的冻结样本和实际使用领域的数据。

落地记录：首版数据准备时，官方 test 的数据服务持续报错。实际 `reference-v1` 从官方 validation 按固定哈希顺序取 48 个不同句子，前 24 个为开发样本、后 24 个为本项目内部保留样本；没有将内部保留样本冒充官方 test。正式规则与下载结果见 [评测标准 v1](text-calibration-benchmark-v1.md)。
