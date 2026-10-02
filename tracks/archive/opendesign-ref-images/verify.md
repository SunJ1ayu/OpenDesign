# Verify: opendesign-ref-images

- Date: 2026-07-02
- Verdict: **PASS**(fast lane 主+submimo 双 PASS;F4 测试缺口已补,14/14 绿)

## Mechanical checks

- [x] tests: test_ds_refs.py 13/13(venv,含 MCP 表面=恰好 4 工具)
- [x] regression: ds_tools 13/13 + ds_organize 18/18 不受影响
- [x] no secrets / unsafe ops:只写 refs-index.md / refs-vocab.md,不碰图片文件,无网络

## Review

- lane: fast(主 + submimo;新模块但纯索引读写,无文件移动/权限面)

### 主 agent 独立 findings(落于读 submimo 输出之前)

倾向 PASS。核对过的点:
1. 编号并发安全:add_ref 在 ds_lock 排他锁内 read→max(r)+1→write,双进程串行化后无重号。
2. link_ref 的 `^- \[r<num>\]` 锚定(整体 bracket 匹配)防 r2 误伤 r12(test_08b);重复
   编号返回 ambiguous_ref。
3. 文件校验 realpath 锁死 refs/ 内:绝对路径/`../`/DS_ROOT 内其他目录均拒(test_06)。
4. 用于字段重写保持 ` | ` 分隔格式(test_07/08 交叉验证 find 能解析 link 后的行)。
5. 已知残余(接受为 deviation):
   a. add_style 追加到 vocab 文件末尾,假设「风格」是最后一节——用户手工在其后加新节会错位;
      代码注释已声明,词表文件头也写明白由工具维护。
   b. 同一图片可被重复登记成两个 r 条目(无查重)——MVP 接受,靠使用纪律,真实用出问题再加。
   c. 索引与图片文件漂移(图删了条目在)——design 已声明接受。

### submimo findings + 仲裁(log: submimo-refs-0702-*.log,修复后 submimo 首次完整交卷)

submimo = PASS + 4 findings + 1 设计观察。仲裁:
- F1 编号原子性依赖 ds_lock 正确性 → 事实正确,锁已单独审过,不动。
- F2 手工编辑索引后 link_ref 可能留尾部空格 → 真实但仅格式被手工破坏时触发,纯外观,收 deviation。
- F3 style 含 `|` 报 style_unknown 语义不精确 → 校验拦得住+错误附词表可自解释,不修(最简)。
- F4 测试缺口 → **收**:补 test_13(空索引 find / 非法 ref_id ""/"abc"/"r0"/"R1" / 多值风格 /
  全角逗号),14/14 绿。
- F5 find 单值查询 vs add 多值不对称 → MVP 接受,查两次即可,收 deviation。

## Accepted deviations

- find_refs 单值查询(多风格查询=多次调用);同图可重复登记(无查重);索引与图片文件漂移
  不巡检;add_style 假设风格节在 vocab 文件末尾;手工破坏索引格式时 link_ref 尾部空格。
  全部为 MVP 取舍,真实使用出现痛点再升级。
