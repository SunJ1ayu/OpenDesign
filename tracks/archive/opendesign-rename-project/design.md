# Design: opendesign-rename-project

- Change: opendesign-rename-project
- Status: final(封闭修复,bind_project 同模式)

## Approach

`rename_project(old, new, ds_root) -> dict`

闸:
- old 过 _resolve(H1)且档案存在 → project_not_found/bad_name/path_escape;
- new 过 _resolve 同闸 + 目标不存在(不覆盖)→ name_taken;old==new → same_name;
- new 额外拒 `| , [ ]`(refs 竖线分段/用于逗号列表/[[链接]] 定界符;NTFS 本就
  禁 |,真实文件夹名零成本)→ bad_name。

执行顺序 = **引用先改(全幂等),档案改名最后(=提交点)**:中途崩 → old 档案
还在,重跑一遍即补齐;反序则崩后 old 已消失无法重跑。
1. clients/*.md + index.md:`[[old]]` → `[[new]]` 精确定界替换(locked_rw 逐文件,
   有命中才写);
2. refs-index.md:"用于:"段逗号列表**精确项**替换(复用 ds_refs._used_segment
   单一真相源解析,不子串误伤 `翡翠湾-18011`);
3. workspace.json:映射键 old→new(值不动;无配置/无该键=跳过;原子写 helper);
4. projects/old.md:首标题行 `# old` 恰好相等才改成 `# new`(自定义 title 不动),
   os.replace 改名(同目录原子)。

返回 {ok, old, new, updated:{title, clients:[..], index, refs:n, workspace}}——
审计清单,助手照它播报。跨文件无整体原子性=接受的 deviation(单用户本地盘,
崩溃窗口毫秒级,重跑补齐),写进文档与返回语义。

## Key trade-offs / risks

- 正文散文里的旧名不改:变更行是账本(只进不删先例),历史读起来仍是当时的名字;
  接受并写进 AGENTS.md 话术(改名后历史沿用旧称是正常的)。
- [[old]] 全文件替换(clients/index)而非仅字段行:[[..]] 是精确定界链接,
  无子串误伤面,散文里的链接也该跟着走。
- 改名后自动绑定直等(文件夹名==key)自然生效,但显式映射仍在且优先——双保险。

## Test strategy (oracle)

RenameProjectOracle:happy 五处齐改+审计清单/new 已存在拒/old 不存在/坏字符
(含 | , [ ])/old==new/自定义 title 保留/refs 多项目列表只换精确项+不误伤
子串前缀/无 workspace 配置照常成功(workspace:false)/幂等语义(引用改后崩
的模拟=重跑成功)。red-check:①去 name_taken 闸→覆盖用例红;②精确项匹配改
子串替换→误伤用例红。verify lane=full panel(写面先例;subglm/submimo 缺席
则记录,主审+subsense 双核)。
