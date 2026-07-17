# Verify: opendesign-cockpit

- Date: 2026-07-17
- Verdict: **PASS**

## Mechanical checks

- [x] pytest 全套 330 passed + 7 skipped(新增 ws 2 + web api 4)
- [x] mjs 全套绿(新 test_cockpit.mjs 9 例先红后绿)
- [x] npm build 绿,dist 进仓(e2e 服务的即最终产物)
- [x] 突变红检 3/3:latest_mtime 恒 None → 2 红;owner 不剥括号 → 1 红;
      projectImages 去 tie-break → 1 红;均还原复绿
- [x] e2e 真 chromium + 真 ds_web 8/8 首跑全过(速览三断言/非模板类目「渲染输出」
      上屏/活跃度/项目图类目小标/图墙常驻入口;临时 DS_ROOT 自清理)
- [x] grep 全 web/src 零模板类目名残留;405 不变量测试重申

## Review

- lane: **fast**(主审 + submimo;只读 UI + 读 API 加性字段,无新写面,
  todo-v3/p6 先例)
- 主审先行(仓外落盘):PASS + 2 观察(fetched stamp 时序=与旧行为等价;
  隐藏列切项目路径实际不可达)
- submimo:**PASS 零 findings**,并独立复核主审两处观察(stamp 去重无脏窗口/
  keyChanged 空值链正确)=交叉验证。零代码改动出审。

## Accepted deviations

- e2e 无 gateway(纯 GET 数据面,聊天不参与;登录/聊天链路 e2e 归 Track E 既有)。
- fetch 失败降级态顶到下个 epoch,无重试(与旧行为等价)。
- 同项目 epoch bump 旧数据顶着无感替换(有意 UX,不闪"读取中")。

## Follow-ups(不阻塞)

- 交付快照块:等首装采纳引擎给类目真相后另 track(plan 合并记录)。
- 图墙项目维度预选:gallery 现无项目维,按真实使用反馈议。
- 扫描成本:dataEpoch 接入后每轮聊天多两次全树扫(路由门已挡隐藏态);
  真机大目录若可感再做缓存,不预优化。

## 用户验收断点

git pull → start.ps1 stop → start.ps1 → Ctrl+F5 回显 **0.24.0**。
验:①点开项目,右列顶部出现速览(阶段 chip/业主/当前状态/最近更新);
②图片区多「项目图」tab(任何文件夹里的图都算,不再只认"06-效果图")+
「图墙 →」常驻;③项目文件每行多"多久前动过";④聊完天右列自动刷新(免切项目)。
