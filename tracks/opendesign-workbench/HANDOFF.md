# HANDOFF — opendesign-workbench（下次会话从这里接）

最后更新：2026-07-06 深夜。**当前状态 = P0 BUILT + verify full lane PASS，
已 commit 待 push 确认后推 GitHub;下一步 = 用户 Windows 机 git pull 实测。**

## 这个 track 交付了什么（P0）

- `bin/ds_web.py`：工作台本地服务（纯 stdlib，8766，只绑 127.0.0.1，纯只读，
  静态 web/dist + /api/todos + /api/health）。
- `web/`：React+TS+Vite 前端（墨侧栏+纸面主区，nanobot 密度；侧栏五模块，
  待办页真数据只读渲染，CAD 修订标签 C<n> 是签名元素）；`web/dist/` 构建
  产物进仓，用户机免 Node。
- `bin/ds_todo.py` 重构：`collect()` 结构化核心（FIELDS_RE 单正则闸门）+
  `render()` 格式化壳，golden 逐字节不变。
- Windows 物料：`bin/ds-web.ps1`（BOM+CRLF+exit code）、install.ps1 钉
  `nanobot-ai==0.2.2 mcp==1.28.1`+pip check、install-windows.md §5b 工作台小节。
- 测试 80 → 92 全绿（+2 collect +10 ds_web，含逃逸 6 变体/symlink/非 UTF-8
  500/中文往返/405+Allow）。

## 用户 Windows 机的验收动作（下次装/更时）

```powershell
git pull
& "D:\AI\OpenDesign\bin\ds-web.ps1"     # 浏览器开 http://127.0.0.1:8766/
python "D:\AI\OpenDesign\tests\test_ds_web.py"
```

递延到真机验证：ds-web.ps1 首跑、msvcrt 写锁窗口内并发读=瞬时 500 的实际观感。

## 评审记录（决策依据全在 design.md 尾部 + verify.md）

- 设计阶段：panel 三审（中文编码盲点）+ sub Claude 二轮（F1 四方共享假阴性
  = ds_todo 无结构化输出,催生 T1 重构）。
- 实现阶段：主自审先行（抓到 _static OSError 真 bug 已修）→ full lane panel：
  MiMo PASS/GLM PASS/SenseNova BLOCK（主项 allow_reuse_address 被解释器实证
  证伪,BLOCK 不成立）。采纳 8 小项全部焊入。
- ⚠️ 工艺：MiMo agent 腿本轮读了 15 文件,质量首次接近 sub Claude;SenseNova
  纯 chat 腿两轮连续误报主项（上轮 oracle #7 空测试、本轮 reuse_address），
  仲裁时对它的"权威引用"要格外核。

## P1-P4 后续（每期另起 track）

P1 聊天（浏览器直连 nanobot ws;token 签发无 CORS → ds_web 至少代理 token
引导;开工首件事=协议基线快照存 docs/）→ P2 日历+重要提醒 → P3 图片规整
（Pillow,新目录副本不动原图）→ P4 3D 查看（工作台内重写,quicklook 只当
参考;动工前提取旧 serve.py hack 清单）。用户可能想调顺序（问过"图片规整
要不要提前",未答）。

## 铁律提醒（项目级）

不出屎山;PKB 写操作必须过 ds_tools 核心（消毒+锁+锚定）,ds_web/前端永远
不直改 markdown;P0 无写面（405 焊死在 oracle）;将来加写端点时加 token。
