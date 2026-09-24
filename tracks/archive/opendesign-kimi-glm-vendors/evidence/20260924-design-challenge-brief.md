# 方案挑战:OpenDesign 模型厂商配置怎么改才不再"扣错家的钱"

仓库:/root/.openclaw/workspace/projects/design-studio(只读;不要读 tracks/opendesign-kimi-glm-vendors/verify.md 和 /root/aiwork/tasks 下任何 *my-direction* / *my-review* 文件)。

## 用户原话(业主,非程序员)
- 「为什么加厂商这个这么难搞 搞了几轮了，不如直接抄zcode」
- 我(主 agent)提议照 ZCode 的做法改:①只留界面一个地方能换厂商/模型(老安装脚本 bin/install.ps1 里手填端点、手填模型两问删掉)②每家厂商各自一格、模型永远带厂商 ③老配置自动转换。业主:「可以 那你开始吧」。
- 此前业主定:要加 Kimi 按量 + GLM 套餐 + GLM 按量(两家 GLM 有同名模型 glm-5.3);以后还要做"自定义厂商"(排最后)。

## 当前行为与证据
- 配置是 nanobot 的 config.json。主槽 `providers.custom`(apiBase + `${DS_LLM_KEY}`,key 在 key.txt)是老启动器(bin/ds-nanobot.ps1、Linux 的 bin/ds-nanobot)唯一认的形状;有外壳(bin/ds_shell.py,装好的正式形态)时第二家起放 `providers.od_<厂商>` + keys/<厂商>.txt,由 `ds_credential.prepare_gateway` 在起网关时写。
- 预设 `model_presets.<名字>.provider` 指 custom 或 od_*;nanobot 按它路由。同名模型按厂商命名(`glm-5.3@glm_plan`)。
- 改配置的入口:界面 save / select_model(bin/ds_credential.py)、prepare_gateway、bin/set_model.py、bin/ds_merge_config.py(被 install.ps1 与 bin/ds_provision.py 调)。
- 最近一轮评审四家都指出的剩余问题:
  #31 老安装脚本可填"认得出的端点 + 别家的共享模型名"(Kimi 端点 + glm-5.3)⇒ 预设裸名 glm-5.3 指 custom ⇒ 发到 Kimi,之后也纠正不了。
  #33 重跑 install.ps1:已有 key.txt 跳过录 key,但还能换端点 ⇒ 新端点配旧 key。
  #32 判据只钉 glm-5.3 一个名字。#35 check-package 必需文件清单漏 ds_credential.py / ds_model.py。

## 拟改变的行为(待挑战)
- install.ps1 不再问端点/模型;ds_merge_config 不再接受 --api-base/--model。
- 主槽端点变更的那一刻(界面存一家新厂商的 key 进主槽),所有指向 custom 且不属于新厂商的预设:主人另有槽 ⇒ 改指它;否则(含认不出主人的裸名、机主手写的)⇒ 删;当前模型悬空 ⇒ 回落新厂商默认。主槽端点不变时手写预设不碰。
- 不把主槽也迁进 od_* 格式(理由:启动链条依赖 key.txt/DS_LLM_KEY)。

## 请回答(先从业主目标推演,再挑战上面的行为;需要就读代码核实)
1. 这个方案完全实现后,业主(或别的装机用户)仍可能怎样"钱扣到另一家"或"聊天连不上"?给具体配置形状。
2. 哪个前提若为假就要重做?(例如:是否还有别的代码路径改 custom.apiBase;是否有用户依赖手填端点)
3. 有没有更简单或更彻底的方向(比如真的把主槽也搬进每家一格)?用什么最小实验能分辨?
不要求 PASS/BLOCK;不用凑问题。用中文回答。
