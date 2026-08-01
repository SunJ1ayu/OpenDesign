# Verify: opendesign-due-writer

- Date: 2026-08-02
- Verdict: <填于收货时>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] `python3 tests/evals/due_writer_eval.py`(本单 oracle)
- [ ] `python3 tests/evals/resolver_eval.py`(旧考卷:动了 docstring 就可能改路由,必跑)
- [ ] pytest 全量 / `node --test tests/*.mjs` / build(本单不碰代码逻辑,做回归兜底)
- [ ] no secrets / unsafe ops

## 判据先行:改任何说明书之前的红检(2026-08-02)

`due_writer_eval.py` 真跑工具循环(每题一个临时 DS_ROOT,模型调什么就真执行什么),
最后**读档案文件**看变更行尾有没有 `⏳YYYY-MM-DD`。基线一跑(原文存
`/tmp/.../due-baseline.txt`,要点抄录如下):

```
ok   ①8月10号之前         → read_project → log_communication → append_change → set_due_date(2026-08-10)
ok   ②这周五之前           → append_change → set_due_date(2026-08-07)
ok   ③下周五前             → append_change → set_due_date(2026-08-14)
ok   ④"尽快"(反例)       → append_change → set_change_status   (没编日期 ✅)
ok   ⑤没提时间(反例)     → append_change                       (没编日期 ✅)
FAIL ⑥一批三条、只有一条带期限 → log_communication → append_change ×3(把"本周五(8/7)前"
                                写进了正文)→ **一次 set_due_date 都没调,档案里 0 个截止日**
probe⑦"月底前"           → log_communication → update_client   (这一跑连变更都没落;
                                上一跑同题是绿的 ⇒ 模型方差,所以它是探针不是计分题)
1 FAIL / 6 计分用例
```

**⚠️ 必须写在最前面的一条:6 题里 5 题本来就绿。**
本单开工前的假设是"助手根本不知道该设截止日",**基线证伪了它** —— 单条意见带明确
或相对期限时,MiMo 现在就会自己调 `set_due_date` 且日期算得对(含"这周五""下周五")。
**这 5 条不是本单的功劳,收货时不许拿它们充数**(T4b 栽过:夹具里混进本来就成立的
断言 = 那条等于没判)。

**本单真正要治的病只有一个,而且正是用户的用法**:设计师**一次贴一大段业主微信**
(⑥ 那种),助手把三条意见都记下来了,却把期限当文字写进正文、**不再回头调
`set_due_date`** —— 硬轨依旧空白。两步调用在"一次一条"时成立,**在批量时断掉**。

**红检还顺手抓到我自己一条判据写错了**(第一版⑥之外的④):原题面写
"厨房吊柜高度**那条**尽快改一下","那条"指代已有条目,助手先 `read_project` 去找是
**合理行为**,红的是我的题面不是它。已改。判据是我写的、可能本身就错——这就是第 5 次。

## Review

- lane: **self**
  > 判据:碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full。本单**一个字节的写口都没动**:
  > `set_due_date`(T2 已过审)、`append_change`(T4b 已过审四腿)签名与实现原样不动,
  > 改的是它们的 **docstring 中文措辞** + `workspace/AGENTS.md` 操作契约 + 新增一份考卷,
  > 外加 `start.ps1` 的**部署同步**(拷文件,不改任何写口)。
  > ⚠️ **升档触发器已预先写死在 design.md**:若考卷证明"两步调用"不可靠,
  > 治法就是给 `append_change` 加 `due` 参数 —— 那是真写口改动,**必须另起一单走 full**,
  > 不许在本单顺手加。
- 派给: **主 agent 直接干**。理由(逐条,不是套话):
  ① 本单的交付物**就是中文职责说明的措辞**,而措辞的唯一裁判是我写的这份 LLM 考卷 ——
  把"写措辞"外包、再由我拿考卷判,brief 里要交代的上下文(用户"不给 llm 加锁"的定调、
  批量掉 due 这个具体病灶、项目的说话口气)比 diff 本身还长,**切碎更贵**,
  正合抽屉里"小而明显的活 = 主 agent 直接干"那一档。
  ② 考卷要**网络 + MiMo key**,codex 腿沙箱禁网**跑不了**,按抽屉的规矩本来就得
  "主 agent 当测试机";这一单的实现量小到不值得为此走一遍派活流程。
  ③ `start.ps1` 那五行在 Linux 上谁都测不了,派出去也只是换个人写没验证过的代码。
  **(分层还账的账仍欠 2 单,记在 [[model-tiering-trial]];本单不硬凑,理由如上。)**
- 规格自查(读任何 panel 输出之前先答):
  **规格错的可能长这样** —— 我把"让截止日有人写"定义成"助手在记录时顺手设",
  但用户真正的用法也许是**事后**在工作台上排期(那样该改的是待办页的批量设期能力,
  不是助手职责)。发现方式只有一个:**真机跑几天后看硬轨里有没有东西、里面的日期
  是不是业主真说过的**。考卷全绿也证明不了这一条,已写进 tasks.md 的待验清单。
  第二种错:考卷题面全是"一句话一件事"的干净口语,真机上的微信原文夹着闲聊、改口、
  "算了不改了"——**考卷绿而真机空**是本单最可能的死法。
- findings:
  - <收货时填>
- arbitrated verdict (主裁): <收货时填>

## Accepted deviations

- **考卷只喂 `ds_tools.py` 的 17 个工具**,不含 `ds_organize` / `ds_refs` 两个 server
  的工具(那两个要另外的执行环境,且与截止日无关)。代价:路由现实感略降 ——
  真机上工具更多、干扰更大。记在这里不当缺陷修。
- **考卷是单轮对话**(设计师一句话 → 助手做完),真机是多轮。同上,不修。
- **模型方差**:同一份考卷两跑之间探针题结果会变(⑦ 一跑绿一跑红)。
  ⇒ 计分题只放稳定题面,收货时**连跑两遍都绿**才算绿。
