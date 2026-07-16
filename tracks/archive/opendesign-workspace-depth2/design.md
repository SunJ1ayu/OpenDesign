# Design: opendesign-workspace-depth2

- Change: opendesign-workspace-depth2
- Status: final(非开放分叉:方向已与用户定死"通用 depth 默认 1、中间层=中性分组",
  不跑 panel-explore;唯一有选项的点是 key 分隔符,是有界工程决策,见 Alternatives)

## Approach

**核心杠杆:`project_dir()` 三级解析的第②级是"文件夹名 == key 直等"——只要
`project_folders()` 返回的 key 自带分组,寻址/路由/文件区/图墙全链零改动。**

1. **config**:`workspace.json` 新增可选 `projectsDepth`。合法值 1|2;缺省=1。
   类型/取值非法 → 整个 config 返回 None(与 root/projects/projectsDir 现行
   同款严格降级,坏配置=功能整体下线,不静默猜)。
2. **扫描**(`ds_workspace.project_folders`):
   - depth=1:现行为,一字不动的语义。
   - depth=2:`projects_root` 下一级 = 分组夹(同款过滤:非点头/过 PROJECT_NAME_RE/
     真目录/不追 symlink);分组夹下一级 = 项目夹(同款过滤)。
   - 返回形状保持 `[(key, realpath)]` 不变(所有消费方免改):depth=2 时
     **key = `"<分组>:<项目名>"`**。排序:分组名序→项目名序。
   - 空分组(下面没合法项目夹)自然不产出条目;分组下的散文件忽略。
3. **key 分隔符 = `":"`**:
   - Windows 文件名**不可能**含 `:`(NTFS 禁),用户真机零碰撞;
   - `_SEG_RE`/`PROJECT_NAME_RE` 本来就放行 `:`,ds_web 项目路由 unquote 后
     匹配(`ds_web.py:236`,前端 `encodeURIComponent` 的 `%3A` 解回 `:`),
     整条 URL 链已验通,不动任何正则/闸;
   - Linux(开发/测试)理论可造带 `:` 的目录:解析顺序保证安全——显式映射
     优先 > 直等(整名含 `:` 的 depth=1 文件夹先命中)> 分组拆分,歧义时
     显式映射兜底纠偏(与 p7 三级绑定同哲学)。
4. **`project_dir()`**:零改动。②直等吃 keyed 名单;③token 子串对 keyed 名单
   照常工作(`2026-0315` 拆 token 也能唯一命中 `2026:0315 某项目`)。
5. **`set_workspace`**(ds_tools):加可选 `projects_depth: int = 0`(0=不传=
   保留旧值,与 projects_dir 同款"显式传优先否则保留");写入 config 仅当
   值为 2(1=默认可省略,写不写等价,选不写保持文件最小)。返回 folder_count
   语义不变(跨分组总项目数)。MCP schema + workspace AGENTS.md 用法段同步:
   助手引导话术=「项目夹直接在根下=不用设;按年份/客户等分了一层=设 2」。
6. **`/api/projects`**(ds_web):unregistered 条目加 `"group"` 字段
   (depth=1 或已建档 = `""`);`name` = 去掉分组前缀的纯项目名。消费集
   realpath 比对逻辑不变(显式映射指向分组内项目夹时照常去重)。
7. **前端**:`api.ts` Project 型加 `group?: string`;Sidebar 项目行在
   unregistered 且有 group 时显示小分组标签(现有 muted 样式,不新造视觉
   系统);其余页面(文件区/图墙/changes)走 key,零改动。

## Key trade-offs / risks

- **key 稳定性**:depth 从 1↔2 切换会改变 unregistered 项目的 key(`名` ↔
  `组:名`)。可接受:unregistered 本来无档案、无持久引用;已建档项目走显式
  映射,key 不受 depth 影响。文档写明。
- **跨分组重名**:`2025/0605 某项目` 与 `2026/0605 某项目` 在 keyed 方案下
  天然不撞(key 含分组)。③token 解析对裸名 `0605-某项目` 会双命中 → 按现行
  "歧义不绑"返回 None,显式映射纠偏——这正是选 keyed 方案的主因。
- **严格 config 校验的翻车面**:手改 config 写了 `"projectsDepth": "2"`(字符串)
  → 整个文件工作区下线。与现行 projectsDir 行为一致,且 set_workspace 工具写入
  的永远是合法 int;文档给正例。
- **性能**:depth=2 扫描 = 分组数 × 一次 scandir,用户量级(5 年 × 每年几十项目)
  毫秒级,不设 cap(项目内类目扫描才有 cap,那层没动)。

## Alternatives considered

- **中间层建模成"年份"字段**:被用户否掉的方向本尊——写死一个人的干法。弃。
- **projects_root 收列表**(`projectsDir: ["2022","2023",...]`):能扫多年但
  逼用户逐年枚举、新年份要手动加;两层扫描零维护。弃。
- **key 用 `/` 分隔**:语义最自然但 `_SEG_RE` 禁 `/`(路径段安全闸),放开要
  动安全正则,翻车面大于收益。弃。
- **key 保持裸项目名、碰撞时才加前缀**:key 不稳定(新分组一出现旧 key 变),
  且碰撞判定要全局扫;keyed 方案恒定可预测。弃。
- **自动探测 depth**(根下全是"纯数字/年份样"目录→猜 2):魔法行为,猜错静默
  错列;显式一行配置成本极低。弃(进 Non-goals)。

## Test strategy (oracle)

主 agent 拥有,先红后绿:

1. `tests/test_ds_workspace.py` 扩展:
   - depth 缺省/=1 → 现行为(既有用例即回归网);
   - depth=2 两分组各两项目 → keyed 名单、名序;分组下散文件忽略;空分组无条目;
   - 分组/项目名不过 PROJECT_NAME_RE → 跳过;symlink 分组/项目 → 跳过;
   - `project_dir` 用 keyed key 直等命中;裸名 token 双命中 → None(歧义不绑);
     显式映射指向分组内项目 → 优先且命中;
   - **red-check(突变验红)**:①把 depth=2 扫描改回一层 → keyed 用例必红;
     ②去掉分组名 PROJECT_NAME_RE 过滤 → 过滤用例必红;
   - config 校验:`projectsDepth` 非 int / 取值 3 / 字符串 "2" → load_config None。
2. `tests/test_ds_tools.py`(set_workspace):传 projects_depth=2 → config 落
   `"projectsDepth": 2` + folder_count 数跨分组;不传 → 保留旧值;传 1 → 不写字段。
3. `tests/test_ds_web_proxy.py`:depth=2 下 /api/projects unregistered 条目
   `key="组:名"`+`group="组"`+`name=纯名`;显式映射消费分组内文件夹 → 去重不重复列;
   `GET /api/files/overview/<组%3A名>` URL 编码往返 200(闸链回归)。
4. `npm run build` 绿(api.ts 类型 + Sidebar)。
5. e2e 不加新剧本(纯后端语义+一个标签,真机验收=用户接入真实两层结构),
   属 accepted deviation,verify.md 记录。
