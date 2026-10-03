# Design: opendesign-ref-images

- Change: opendesign-ref-images
- Status: frozen(2026-07-02 用户三答落定:来源=小红书/Pinterest/Behance/谷德/印际;
  词表=空间锁死+风格半开放;打标=MVP 人工口头,MiMo 视觉自动打标留 P-later 验证)

## Approach

新模块 `bin/ds_refs.py`,照 ds_tools.py 范式(纯 Python 核心 + 末尾 FastMCP stdio 包装、
词表校验、ds_lock 锁、不删行、`r<n>\b` 锚定)。**工具只管索引,不碰图片文件本身**
(文件移动走 organize 确认闸,不新开写文件能力)。

### 数据

- **图库**:`DS_ROOT/refs/<风格>/<空间>/xxx.jpg` —— 文件母本池,人(或以后 organize)放。
- **索引**:`DS_ROOT/refs-index.md` —— 每图一条,首次使用自动建:
  `- [r<n>] <风格>|<空间>[,空间2] | 来源:<自由文本> | 文件:<refs/ 相对路径,存储用 / 分隔符> | 用于:<项目slug,逗号分隔> | 备注:<自由文本>`
  末行 `最后更新: YYYY-MM-DD`。条目只增不删。
- **词表**:`DS_ROOT/refs-vocab.md`,首次使用自动建,两节:
  - `## 空间(锁死)`:玄关/客厅/餐厅/厨房/中西厨/主卧/次卧/儿童房/老人房/书房/主卫/客卫/
    衣帽间/阳台/家政区/影音室/健身房/走廊/庭院/全屋 —— 工具不提供新增入口,改=改文件。
  - `## 风格(半开放)`:奶油风/侘寂风/法式/现代简约/极简/轻奢/新中式/中古风/原木风/
    工业风/美式/日式/北欧/复古/混搭 起步;`add_style` 工具可增(AGENTS.md 约定:新增前
    先跟设计师确认——纪律在 prompt 层,词表污染风险低,不上硬闸)。

### 工具(MCP 4 个)

1. `add_ref(file, style, space, source, note)` — 登记:词表校验(风格/空间可逗号分隔多值)、
   文件必须真实存在于 refs/ 内(realpath 防逃逸+防手误)、自动编号 max(r)+1。
2. `find_refs(style, space, project, keyword)` — 全部可选,AND 过滤,返回命中行;空参=全量。
3. `link_ref(ref_id, project)` — 记"用于某项目":`\br<n>\b` 锚定、项目文件必须存在、去重追加。
4. `add_style(style)` — 风格词表新增(幂等)。

## Key trade-offs / risks

- 索引与文件可能漂移(图删了索引还在)→ 接受;MVP 不做一致性巡检,真实使用后按需加。
- 一图多风格/多空间:MVP 允许逗号多值,检索按 token 匹配;不做权重/主次。
- 来源字段自由文本不锁词表(小红书/Pinterest/Behance/谷德/印际/业主提供…),检索用 keyword 兜。
- 路径存储统一 `/` 分隔符 → Windows/Linux 索引互通。

## Alternatives considered

- 参考图跟项目放 —— 否:复用查找碎;母本池+索引"用于"字段两头都成立(用户 07-02 已认)。
- 每图一个 sidecar md —— 否:几百图=几百文件,grep/浏览都碎;单索引文件+锚定编号够用。
- 视觉自动打标进 MVP —— 否:MiMo 看图能力未验证,先人工;自动化另立验证任务(用户同意)。
- 硬闸管 add_style —— 否:词表污染风险低且可逆,prompt 纪律够;硬闸留给动文件的操作。

## Test strategy (oracle)

`tests/test_ds_refs.py`,零依赖 tmpdir,主 agent 所有:
① add 正常(r1、格式、索引自动建、最后更新)② 编号连续 ③ 风格/空间不在词表→拒+零改动
④ add_style 后放行、幂等 ⑤ 空间词表无新增入口(unknown 恒拒)⑥ 文件不存在→file_not_found;
`../` 逃逸→path_escape ⑦ find 按风格/空间/项目/keyword 过滤+空参全量 ⑧ link 正常+去重+
r2 不误伤 r12+ref/项目不存在→拒 ⑨ 任何操作不减少条目数 ⑩ 多空间逗号值 ⑪ 路径存储为 /
⑫ MCP 表面恰好 4 工具。verify lane = fast(主 + submimo,顺便实战验证 submimo 修复)。
