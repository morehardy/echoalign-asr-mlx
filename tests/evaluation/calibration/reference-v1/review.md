# 开发集音频与参考文本复核

以下顺序优先列出严格词面 WER 有差异的片段，然后列出零差异片段。所有样本本项目复听状态均为 `pending`。请以音频核对，不能仅根据 ASR 输出改参考。保留集不在此表中。

本文件记录原始 ASR 基线。之后按现有方案运行的校准没有产生实际修改，结果见[校准评测报告](runs/policy-1-qwen3.5-4b-4bit/REPORT.md)。数字或缩写形式差异需要独立判断，不直接视为实际语义错误。

## 1. 句子 1614 · 词面编辑数 3

[音频](audio/dev/fleurs-en-dev-1614-16807981165307472350.wav) · [参考 TXT](references/dev/fleurs-en-dev-1614-16807981165307472350.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1614-16807981165307472350.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1614-16807981165307472350.srt)

参考：They can see very well in the dark with night vision, and move very stealthily, too. Ocelots hunt their prey by blending in with their surroundings then pouncing on their prey.

ASR：They can see very well in the dark with night vision, and move very stealthily too. Also, lots hunt their prey by blending in with their surroundings and pouncing on their prey.

复听：待完成。

## 2. 句子 1555 · 词面编辑数 2

[音频](audio/dev/fleurs-en-dev-1555-6037648224035961543.wav) · [参考 TXT](references/dev/fleurs-en-dev-1555-6037648224035961543.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1555-6037648224035961543.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1555-6037648224035961543.srt)

参考：In the churchyard, there are interesting marble sculptures of doves over some tombs.

ASR：In the churchyard, there are interesting marble sculptures of some of doves over some tombs.

复听：待完成。

## 3. 句子 1566 · 词面编辑数 2

[音频](audio/dev/fleurs-en-dev-1566-9005815195429653356.wav) · [参考 TXT](references/dev/fleurs-en-dev-1566-9005815195429653356.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1566-9005815195429653356.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1566-9005815195429653356.srt)

参考：Yet eighty percent of our goods were taxed through tariffs in Central American countries. we treat you.

ASR：Yet 80% of our goods were taxed through tariffs in Central American countries. We treat you.

复听：待完成。 **需要数字/缩写归一化复核。**

## 4. 句子 1602 · 词面编辑数 2

[音频](audio/dev/fleurs-en-dev-1602-15006047853740326323.wav) · [参考 TXT](references/dev/fleurs-en-dev-1602-15006047853740326323.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1602-15006047853740326323.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1602-15006047853740326323.srt)

参考：Majorcan cuisine, like that of similar zones in the Mediterranean, is based on bread, vegetables and meat (specially pork), and uses olive oil throughout.

ASR：Majorcan cuisine, like that of similar zones in Mediterranean, is based on bread, vegetables and meat, specifically pork, and uses olive oil throughout.

复听：待完成。

## 5. 句子 1625 · 词面编辑数 2

[音频](audio/dev/fleurs-en-dev-1625-7383904139424536248.wav) · [参考 TXT](references/dev/fleurs-en-dev-1625-7383904139424536248.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1625-7383904139424536248.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1625-7383904139424536248.srt)

参考：Famous singers across the country presented bhajans, or devotional songs, to Shri Shyam's feet.

ASR：Famous singers across the country presented bhajans or devotional songs to Sheer Shah's feet.

复听：待完成。

## 6. 句子 1522 · 词面编辑数 1

[音频](audio/dev/fleurs-en-dev-1522-8364006913180567866.wav) · [参考 TXT](references/dev/fleurs-en-dev-1522-8364006913180567866.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1522-8364006913180567866.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1522-8364006913180567866.srt)

参考：Technology offers the solution with virtual field trips. Students can look at museum artifacts, visit an aquarium, or admire beautiful art while sitting with their class.

ASR：Technology offers a solution with virtual field trips. Students can look at museum artifacts, visit an aquarium, or admire beautiful art while sitting with their class.

复听：待完成。

## 7. 句子 1591 · 词面编辑数 1

[音频](audio/dev/fleurs-en-dev-1591-13837548118133175593.wav) · [参考 TXT](references/dev/fleurs-en-dev-1591-13837548118133175593.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1591-13837548118133175593.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1591-13837548118133175593.srt)

参考：Former House Speaker Newt Gingrich, Texas governor Rick Perry, and Congresswoman Michele Bachmann finished in fourth, fifth, and sixth place, respectively.

ASR：Former House Speaker Newt Gingrich, Texas Governor Rick Perry, and Congresswoman Michelle Bachmann finished in fourth, fifth, and sixth place, respectively.

复听：待完成。

## 8. 句子 1605 · 词面编辑数 1

[音频](audio/dev/fleurs-en-dev-1605-10511964668971448587.wav) · [参考 TXT](references/dev/fleurs-en-dev-1605-10511964668971448587.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1605-10511964668971448587.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1605-10511964668971448587.srt)

参考：Due to the long distance from the continent mammals were unable to make the journey making the giant tortoise the primary grazing animal in the Galapagos.

ASR：Due to the long distance from the continent, mammals were unable to make the journey, making the giant tortoise the primary grazing animal in the Gobios.

复听：待完成。

## 9. 句子 1519 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1519-16685771406658302555.wav) · [参考 TXT](references/dev/fleurs-en-dev-1519-16685771406658302555.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1519-16685771406658302555.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1519-16685771406658302555.srt)

参考：In many cases, enrolling on a gap-year course abroad can actually improve your chances of moving into higher education back in your home country.

ASR：In many cases, enrolling on a gap year course abroad can actually improve your chances of moving into higher education back in your home country.

复听：待完成。

## 10. 句子 1521 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1521-11840539862172308240.wav) · [参考 TXT](references/dev/fleurs-en-dev-1521-11840539862172308240.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1521-11840539862172308240.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1521-11840539862172308240.srt)

参考：The satellite in space gets the call and then reflects it back down, almost instantly.

ASR：The satellite in space gets the call and then reflects it back down almost instantly.

复听：待完成。

## 11. 句子 1534 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1534-7552355741824675369.wav) · [参考 TXT](references/dev/fleurs-en-dev-1534-7552355741824675369.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1534-7552355741824675369.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1534-7552355741824675369.srt)

参考：Combined with its relative inaccessibility, "Timbuktu" has come to be used as a metaphor for exotic, distant lands.

ASR：Combined with its relative inaccessibility, Timbuktu has come to be used as a metaphor for exotic, distant lands.

复听：待完成。

## 12. 句子 1535 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1535-16038225777468807850.wav) · [参考 TXT](references/dev/fleurs-en-dev-1535-16038225777468807850.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1535-16038225777468807850.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1535-16038225777468807850.srt)

参考：It uses satellite-based technology as opposed to older ground-radar-based technology to allow air traffic controllers to pinpoint aircraft with greater precision and give pilots more accurate information.

ASR：It uses satellite-based technology, as opposed to older ground radar-based technology, to allow air traffic controllers to pinpoint aircraft with greater precision and give pilots more accurate information.

复听：待完成。

## 13. 句子 1543 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1543-15171241960492149561.wav) · [参考 TXT](references/dev/fleurs-en-dev-1543-15171241960492149561.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1543-15171241960492149561.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1543-15171241960492149561.srt)

参考：The patient had been to Nigeria, where some cases of the Ebola virus have occurred.

ASR：The patient had been to Nigeria, where some cases of the Ebola virus have occurred.

复听：待完成。

## 14. 句子 1545 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1545-5260885647261312884.wav) · [参考 TXT](references/dev/fleurs-en-dev-1545-5260885647261312884.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1545-5260885647261312884.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1545-5260885647261312884.srt)

参考：A curry can be either "dry" or "wet" depending on the amount of liquid.

ASR：A curry can be either dry or wet, depending on the amount of liquid.

复听：待完成。

## 15. 句子 1551 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1551-4023494736730069902.wav) · [参考 TXT](references/dev/fleurs-en-dev-1551-4023494736730069902.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1551-4023494736730069902.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1551-4023494736730069902.srt)

参考：They are still trying to determine just how large the crash was and how the Earth will be affected.

ASR：They are still trying to determine just how large the crash was, and how the Earth will be affected.

复听：待完成。

## 16. 句子 1565 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1565-9466009236386247443.wav) · [参考 TXT](references/dev/fleurs-en-dev-1565-9466009236386247443.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1565-9466009236386247443.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1565-9466009236386247443.srt)

参考：Science’s main goal is to figure out the way the world works through the scientific method. This method in fact guides most scientific research.

ASR：Science's main goal is to figure out the way the world works through the scientific method. This method, in fact, guides most scientific research.

复听：待完成。

## 17. 句子 1569 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1569-6698602092091460070.wav) · [参考 TXT](references/dev/fleurs-en-dev-1569-6698602092091460070.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1569-6698602092091460070.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1569-6698602092091460070.srt)

参考：The Report opens with plea for open debate and the formation of a consensus in the United States about the policy towards the Middle East.

ASR：The report opens with plea for open debate and the formation of a consensus in the United States about the policy towards the Middle East.

复听：待完成。

## 18. 句子 1573 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1573-10606824155904794190.wav) · [参考 TXT](references/dev/fleurs-en-dev-1573-10606824155904794190.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1573-10606824155904794190.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1573-10606824155904794190.srt)

参考：A satellite phone is not generally a replacement for a mobile phone, as you have to be outdoors with clear line of sight to the satellite to make a phone call.

ASR：A satellite phone is not generally a replacement for a mobile phone, as you have to be outdoors with clear line of sight to the satellite to make a phone call.

复听：待完成。

## 19. 句子 1574 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1574-4418066175314133039.wav) · [参考 TXT](references/dev/fleurs-en-dev-1574-4418066175314133039.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1574-4418066175314133039.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1574-4418066175314133039.srt)

参考：The winter can be deceptively chilly: temperatures rarely go below freezing, but the wind and humidity combine to make it feel colder than what the thermometer says.

ASR：The winter can be deceptively chilly. Temperatures rarely go below freezing, but the wind and humidity combine to make it feel colder than what the thermometer says.

复听：待完成。

## 20. 句子 1577 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1577-5546513999592253497.wav) · [参考 TXT](references/dev/fleurs-en-dev-1577-5546513999592253497.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1577-5546513999592253497.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1577-5546513999592253497.srt)

参考：That didn't seem to make sense to me; it certainly wasn't fair.

ASR：That didn't seem to make sense to me. It certainly wasn't fair.

复听：待完成。

## 21. 句子 1583 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1583-10493474598526206030.wav) · [参考 TXT](references/dev/fleurs-en-dev-1583-10493474598526206030.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1583-10493474598526206030.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1583-10493474598526206030.srt)

参考：She came to this conclusion due to the multitude of positive comments and encouragement sent to her by both female and male individuals urging that contraception medication be considered a medical necessity.

ASR：She came to this conclusion due to the multitude of positive comments and encouragement sent to her by both female and male individuals, urging that contraception medication be considered a medical necessity.

复听：待完成。

## 22. 句子 1587 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1587-1105184381995491301.wav) · [参考 TXT](references/dev/fleurs-en-dev-1587-1105184381995491301.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1587-1105184381995491301.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1587-1105184381995491301.srt)

参考：The first cases of the disease this season were reported in late July.

ASR：The first cases of the disease this season were reported in late July.

复听：待完成。

## 23. 句子 1595 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1595-14225189458852066857.wav) · [参考 TXT](references/dev/fleurs-en-dev-1595-14225189458852066857.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1595-14225189458852066857.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1595-14225189458852066857.srt)

参考：The Tibetan Buddhism is based on the teachings of Buddha, but were extended by the mahayana path of love and by a lot of techniques from Indian Yoga.

ASR：The Tibetan Buddhism is based on the teachings of Buddha, but were extended by the Mahayana path of love and by a lot of techniques from Indian yoga.

复听：待完成。

## 24. 句子 1611 · 词面编辑数 0

[音频](audio/dev/fleurs-en-dev-1611-7644436983984138819.wav) · [参考 TXT](references/dev/fleurs-en-dev-1611-7644436983984138819.txt) · [辅助 SRT](references/dev/fleurs-en-dev-1611-7644436983984138819.srt) · [ASR 字幕](runs/raw-asr/dev/fleurs-en-dev-1611-7644436983984138819.srt)

参考：. Scientists say this animal's plumage was chestnut-brown on top with a pale or carotenoid-colored underside.

ASR：Scientists say this animal's plumage was chestnut brown on top, with a pale or carotenoid-colored underside.

复听：待完成。
