# Design: opendesign-client-tools

- Change: opendesign-client-tools
- Status: final(无开放架构分叉,不跑 panel-explore——两工具的形态审计已给定,
  唯一自由度是 update 语义,下面逐条拍板)

## Approach

镜像既有 ds_tools 姿势,零新依赖、零新文件:

### read_client(name)

与 read_project 逐行同构:`_resolve(ds_root, "clients", name)`(realpath allowlist +
PROJECT_NAME_RE 字符集闸,业主名与项目名共用同一咽喉)→ 不存在返回
`{"error": "client_not_found"}` → 原文整读返回 `{"ok": True, "content": ...}`。
**不做结构化解析**:read_project 的先例就是原文返回,LLM 自己读 markdown;
解析层=多一处会漂移的格式真相源,不值。

### update_client(name, field, value)

- **字段白名单两档语义**:
  - `联系方式/预算区间/风格偏好/关键约束/决策习惯` → **替换**头部字段行的值
    (`^- {field}[::]` 定位,只认首个 `## ` 段头之前的头部区;行缺失(手建档案)
    则在头部区末尾**补插**,action="inserted");
  - `备注` → **追加**一行 `- {today} {value}` 到 `## 备注` 段尾(自由文本区,
    积累不覆盖;段缺失自动补建,同 log_communication 先例);带日期=账本纪律,
    "业主雷区是什么时候说的"可追溯。
  - 其余 field → `{"error": "bad_field", "fields": [...]}`(返回可用清单,自愈回路)。
- **`关联项目` 不在白名单**(机器管理:create_project 写入、rename_project 五处
  联动、delete_project 清点;LLM 自由改写会打断记账)。
- **value 消毒 + 拒空**:sanitize_field 折换行(多行 value = 伪造字段行/段头,
  7-03 盲评铁律);空 value 返回 `empty_value`(清空字段是罕见操作,静默清空
  比显式拒绝更危险;要清让设计师说"改成 无")。
- **锁**:ds_common.locked_rw 读改写(同 append_change)。
- **无页脚 bump**:client 档案 SCHEMA 无 `最后更新:` 页脚(超期提醒只看项目),
  不引入。
- 返回 `{"ok": True, "client", "field", "action": "replaced"|"inserted"|"noted"}`。

### 路由(docstring + AGENTS.md)

- `read_client`:被问业主情况/开工回顾偏好时用;docstring 列出档案里有什么。
- `update_client`:业主信息变了(预算/偏好/联系方式)或听到值得记的性格雷区
  (→ field=备注)时用。**教训(tool-audit):禁止句里别写典型场景关键词**——
  "关联项目改不了"表述为"改项目归属用 rename_project/create_project",不写反向句。
- AGENTS.md 工具表加两行;规则 4"业主档案"话术顺带指向新工具。

### resolver eval

- 暗区探针 `?业主王姐的电话是多少 → None` **翻转为计分断言 → read_client**;
- 新增 update_client 断言 2 条(改字段/记雷区);跑一轮全绿才算完。

## Key trade-offs / risks

- 替换语义会整行覆盖旧值(如联系方式旧号码被抹):接受——字段行是"当前值"
  语义,历史在对话/沟通日志里;备注档提供积累通道。
- 手建档案字段行缺失时补插,插入位置=头部区末尾:确定性,但与模板顺序可能
  不一致——无解析依赖顺序,接受。
- 业主名与项目名共用 PROJECT_NAME_RE:业主名不含 `/ \` 等本就是既有约束
  (create_client 已走 _resolve),无新限制。

## Alternatives considered

- read_client 返回结构化 dict(逐字段解析)→ 拒:多一处格式真相源,
  read_project 先例是原文返回,LLM 消费端无需结构化。
- update_client 拆成 update_field + add_note 两工具 → 拒:工具数膨胀伤路由
  (18→20 已到边),一个工具两档语义靠 field 值区分,docstring 说得清。
- 备注不带日期 → 拒:全库账本纪律都带日期,追溯价值 > 一行整洁。

## Test strategy (oracle)

tests/test_ds_tools.py 两套件,先红后绿 + 突变红检:

- ReadClientOracle:正常读回(内容逐字节=盘上文件)/ client_not_found /
  path_escape(`../x`)/ bad_name(`a/b`,H1 同款)。
- UpdateClientOracle:
  1. 替换:改预算区间 → 该行变、其余行逐字节不动;
  2. 补插:手建档案缺字段行 → 头部区末尾插入,不碰段落;
  3. 备注追加:两次调用 → 两行都在、带日期、顺序稳定;`## 备注` 段缺失自动补建;
  4. 白名单:`关联项目` / 随便编的 field → bad_field + fields 清单;
  5. 拒空:value=""(或纯空白)→ empty_value,文件零改动;
  6. 注入:value 带 `\n## 伪段头` / `\n- [待确认] C9 ...` → 折叠成单行,
     grep 不到行首伪段头/伪变更行(红检:去掉 sanitize 必红);
  7. 错误契约零副作用:所有 error 路径文件 mtime/内容不变。
- 突变红检:注释掉白名单校验 → 4 红;去掉 sanitize_field → 6 红。
- resolver eval 16+3 全绿(网络依赖,不进 pytest,单独跑记录 verify.md)。
