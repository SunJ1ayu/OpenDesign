# Verify: opendesign-workbench-p7

- Lane: fast(主审 + submimo;subglm 双腿 key 故障、subsense 连续两轮盲评无信号,
  均缺席本轮,已记工具债)
- Verdict: **PASS**(合议:主审 PASS + submimo LGTM)

## Oracle(dispatch 前已跑,全绿)
- py 13 套件全 OK:workspace 30(3 突变红检:唯一命中/charset/projectsDir within)、
  proxy 13(3 突变红检:CT 闸/key 闸/路由锚定)、api 25、web 14、files 23、
  todo/tools/refs/set_model/merge_config/skills/organize/lock。
- mjs 4 文件 0 fail(connection 新增 init 透传+Authorization 不可覆盖)。
- e2e 真 gateway+真 MiMo 3/3 首跑 ALL PASS(截图 /root/aiwork/logs/odw-p7-shots):
  ①未建档文件夹进列表带标、已映射文件夹不重复;②建档引导+#key 文件区类目可读;
  ③聊一轮→悬停✕→confirm→行消失→sessions API 无该 key(真删除)。
  测完 config 已还原(websocket disabled+token 空),端口清。

## 主审(先行,/root/aiwork/tasks/opendesign-p7-review-my-review.md)
- 自查抓到并修 1 处:_delete_session docstring 与 _proxy 查询串透传矛盾
  (delete_automations 可经 query 透传=机主既有能力非越权面,修文档不加剥离)。
- 自查核过:SearchPanel 对未建档 key 的 404 有每项目 .catch 容错不打断索引;
  GalleryPage refs 未知 key 返回空列表。

## 仲裁(逐条,基于代码核验)
- submimo「_proxy 硬编码 GET,将来上游要真 POST 会踩」→ 核实为真
  (ds_web.py _proxy conn.request("GET")),收:已加注释钉住契约。
- submimo「✕ 是 span role=button 无键盘处理」→ 核实为真;拒(记 deviation):
  HTML 不允许 button 嵌套,桌面鼠标优先,与现版行内交互习惯一致。
- submimo 其余 5 个 focus 区全 LGTM,与主审结论一致;双 PASS 不降主审自己的bar,
  安全面(CSRF/走私/405 锁)主审已亲手突变验红。

## Accepted deviations
- 删除当前正续聊的会话后已渲染 transcript 不清(与 p3「新对话不重置」同语义);
  继续发消息会以同 key 重建会话。
- token 绑定数字子串误绑窗口(如 2302⊂23021 唯一命中):显式映射优先可纠偏,v1 不做词边界。
- 文件夹名含白名单外字符(&、全角符号等)不列(诚实降级,等真实数据再放宽)。
- ✕ 删除键无键盘可达性(见仲裁)。
- 并发删除与列表竞态、删除当前活动 ws 会话无专测(既有 epoch/ws 生命周期模式)。

## 用户验收断点(Windows)
git pull → start.ps1 → 设置弹层回显 **0.8.0** →
①侧栏项目列表直接出现 D 盘项目文件夹(workspace.json 只需 root;未建档带标,
点开文件区/图墙可用);②历史对话行悬停出现 ✕,删除后列表即时消失。
