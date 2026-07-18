# Verify: opendesign-adoption

- Date: 2026-07-17（收口 2026-07-18）
- Verdict: PASS

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subdeepseek/subglm/subkimi,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(采纳引擎=产品脊梁级)。

## Mechanical checks

- [x] build passes（纯后端 Python + 版本号在 ds_web.py,经 /api/health 服务,无 web/src 改动→dist 不需重建）
- [x] tests pass
  - oracle test_ds_adopt 15/15;回归 test_ds_organize 22(1 skip=mcp 未装)/
    test_ds_intake 23/test_ds_lint 24/test_ds_tools/test_ds_web_proxy 13/test_ds_web_intake 10 全 OK
  - mjs 单元 8/8;resolver eval 27/27
  - **e2e tests/e2e/adoption.e2e.py**:散文件→adopt_scan(只读)→stage_adoption(auto→plan/
    suggest→advice/未知→skipped)→未批准 apply 被物理拒(not_approved)→真起 ds-approve 子进程
    →apply 落位。断言 pdf→项目内 01-资料/、jpg→工作区级 参考图库/(scope 正确)、
    被引用 dwg 岿然不动、未知 xyz 未碰。ALL PASS
- [x] no secrets / unsafe ops（零新写面:adopt_scan 纯读;stage_adoption 唯一写=经 stage_plan
      既有校验闸;approve 仍是人的专属,MCP 无 approve 工具,pin 测试保留）

## Review

- lane: full(主审 + submimo + subdeepseek + subglm + subkimi)
- findings:
  - 主审(写于读任何 employee 前,tasks/opendesign-adoption-my-review.md):PASS 零必改,
    留 _read_staged 读回 / stage_plan src/dst 衔接两点请 panel 复核。
  - submimo PASS(2 nit:AGENTS.md 未盖 0.26.0 版号=版号在 ds_web.py 属实/_read_staged
    静默取舍=可接受)。
  - subdeepseek(agent 腿)PASS,亲验 oracle 逐字节未动。
  - subglm(chat 腿,GLM-5.2)PASS + 抓到 1 真 LOW:_read_staged 列表推导在 try 外,
    plan JSON 合法但结构异常(缺键/非 dict)时 KeyError/TypeError 逃逸,stage_adoption
    在 plan 已落盘后崩。→ **已修**(推导移入 try,捕获扩 KeyError/TypeError,降级语义不变;
    785dbc9)。这是本轮 panel 唯一新增真信息,正是主审第 4 点请复核处的实锤。
  - subkimi(K3)PASS,五条安全要求逐条核过(Bash 被守卫拦=设计如此,自述限制)。
- arbitrated verdict(主裁):**PASS**。四腿 unanimous PASS 未降低主审自有 bar;subglm 的
  LOW 已按主审独立复核确认为真并修复,修后 oracle 15/15 + 回归全绿。

## Accepted deviations

- stage_adoption 的 taxonomy_bad/project_unreadable 两个防御性 error 超出 design 枚举——
  不可达路径的诚实降级,无害。
- depth2 跨分组同名项目夹在报告里按 basename 重列(v1 可接受,真机 depth2 场景本就异常)。
- 版本号只在 ds_web.py(经 /api/health 回显),AGENTS.md 不再各自钉版号=单一真相源,非缺陷。
