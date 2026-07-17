# Design: opendesign-set-stage

- Change: opendesign-set-stage
- Status: final(无架构分叉;姿势全部复用 client-tools 刚验证过的模式)

## Approach

- `PROJECT_STAGES = ("洽谈","量房","平面方案","方案深化","效果图","施工图",
  "施工交底","施工跟进","软装","竣工验收","售后")` —— 词表常量进 ds_tools.py,
  与 AGENTS.md「阶段词表」段一致(代码为真相源)。
- `set_stage(project, stage, ds_root, today=None)`:
  - sanitize stage → **词表精确匹配**,不中返回 `{"error":"bad_stage","stages":[...]}`
    (自愈清单,同 bad_field 先例)。注入面由构造消灭:折行后不在词表=拒,
    永远只有词表字面量能落盘。
  - `_resolve(projects)` 闸 → not_found → locked_rw 读改写:
    头部区(首个 `## ` 前)定位 `^- 阶段[::]` 替换(缺行补插,同 update_client);
    **bump_last_updated**(项目档案有页脚,推进阶段=有动静,超期计时重置——
    与 append_change 等项目写工具一致;client 档案无页脚故 update_client 不 bump,
    两者不同是有意的)。
  - 返回 `{"ok", "project", "stage", "prev"}`(prev=旧阶段或 null,播报用)。
- MCP docstring:何时用(项目推进/设计师说到了新阶段)+ 词表全列。
- AGENTS.md:工具表一行;「阶段词表」段加一句"推进用 set_stage"。

## Key trade-offs / risks

- 阶段可任意跳/可回退(不强制词表顺序):现实如此(返工回效果图、跳过软装),
  顺序校验=假保护,不做。
- 词表两处存在(代码+AGENTS.md 散文):AGENTS.md 是给 LLM 读的话术,代码是闸;
  漂移时闸赢(错话术顶多多一次 bad_stage 自愈)。

## Test strategy (oracle)

SetStageOracle:①替换+prev+页脚 bump ②bad_stage+清单+零改动 ③not_found
④bad_name ⑤缺行补插 ⑥注入(带换行/伪段头的 stage 折行后必不在词表→拒,零改动)
⑦同阶段幂等。突变红检:词表校验注掉→⑥②红。resolver eval +1 条。
