# Verify: opendesign-workbench-p5

- Date: 2026-07-13
- Verdict: **PASS**(主审 + submimo 双 PASS;subsense 无信号、subglm 双腿缺席,见 Review)

## Mechanical checks

- [x] build passes(vite build + `tsc --noEmit` 零错;dist 进仓,VERSION 0.6.0)
- [x] tests pass(py 168 passed 7 skipped 全量;mjs 47/47 含 gallery 7 条;
      突变红检:ds_workspace 去 within×2/去扩展过滤 → 红 5/3/3;
      ds_web 去 within 闸 → 红 2、绕 resolve_sub → 红 1;CSRF 测试先红后绿)
- [x] no secrets / unsafe ops(workspace.json/e2e-workspace 已 gitignore;
      open-folder 为唯一非 GET,受控例外见主审红线 #1/#2)

## e2e(真 gateway + 真模型,ds-web 0.6.0)

9/9 首跑全绿:登录→3a / 2a 文件区类目计数 1/1/3 / 最近更新 8 行 /「打开文件夹」→
DS_OPEN_CMD 记录器收到项目根 / 类目行→ …/03-CAD / 图墙 6 格(2 refs+4 工作区图)+
来源/空间/风格 chips / 空间「客厅」筛到 1 格再取消恢复 6 / lightbox 开+Esc 关 /
聊天发送→真模型回复(主链路零回归)。截图 /root/aiwork/logs/odw-p5-shots/。
环境:enable_webui 临时 token + 仓根 DS_ROOT + e2e-workspace 夹具(taxonomy v1.0)
+ refs 用 ds_refs 工具登记;测完 config 已还原(websocket disabled+token 空),端口清。

## Review

- lane: **full**(POST 写方法针孔 = 只读铁律例外 + 新文件读出面,security 触发)
- 主审(先于读任何 panel 输出落盘):/root/aiwork/tasks/opendesign-p5-review-my-review.md
  —— verdict PASS;5 红线亲手核(POST 针孔唯一性/open-folder 闸序/files-file 三闸
  等强 refs/扫描 symlink 不走入/前端注入面);自查抓到 open-folder CSRF simple-request
  面并当场焊死(3101cb6,红检过)。
- panel(日志 /root/aiwork/logs/panel-opendesign-p5.*):
  - **submimo:PASS 零阻塞**,完整交卷(十个安全面全过:POST 针孔九层闸零绕过/
    files-file 与 refs 三闸等强/symlink follow=False/前端 JSX 转义+逐段编码/CSRF/
    Popen 列表无 shell/降级与 404 不回显)。5 条 nit 仲裁:**收 3**(_scan OSError
    docstring、尾换行 \Z 红测、404 不回显断言——核对 refs 先例属实,4232afb);
    **拒 2**("foo..bar 误拒"= P2 起已文档化的保守纵深,非本 track 引入;"缺中文文件
    名服务测试"= 夹具 02-参考图/客厅参考.png 即中文路径,test_serves_image 已覆盖)。
    另一观察"仓内无 e2e 文件"= 项目惯例(driver 在 scratchpad,结果+截图进 verify),拒。
  - **subsense:无信号**(chat 腿盲评复发:commit 已提交→git diff 空→
    NEEDS_MORE_INFO。与 p4 同型;"diff 空自动 INCLUDE"工具债再 +1,记忆已挂账)。
  - **subglm:双腿缺席**——agent 腿 rc=1(本会话 ANTHROPIC_API_KEY 环境冲突,
    非代码问题);回退 chat 腿百炼 key 401 invalid_api_key 空转,人工终止无交卷。
    key 失效为工具链问题,另行修复,不阻塞本 track(7-03 缺席先例)。
- findings 仲裁:全部逐条核代码给依据(见上),无 BLOCK 级存活。
- arbitrated verdict (主裁): **PASS** —— 主审(5 红线亲手核+自查修 CSRF)与 submimo
  完整审一致;oracle 在 panel 发车前 rc=0(panel-opendesign-p5.launch.log);
  出席 2/4 方但均为深度审,缺席两方均系基建故障而非审出问题。

## Accepted deviations

- 图墙无缩略图,原图直出 + lazy(proposal 非目标;性能真痛再做)。
- overview 每类目 2000 上限截断后 recent 可能漏文件(诚实 capped,家装量级足够)。
- /api/files/file 可读项目夹内任意白名单扩展图片,不限 images 清单(同信任域,
  扩展+within 双闸,与 refs 静态服务同风险面)。
- workspace.json 手编(将来首装采纳引擎生成;example 模板已给)。
