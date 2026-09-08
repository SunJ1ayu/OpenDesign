# 探针:更新时跑 provisioning,到底会不会改动 `UserData\` 的字节?

- 日期:2026-09-08(接手断线后)
- 起因:design 里写着「`OpenDesign.nsi:143` 每次安装都跑 provisioning、往 `UserData\` 写
  ⇒ 死线『`UserData\` 逐字节不变』**结构上永远绿不了**」。
  那句**前半是读来的**(源码确实这么写),**后半是推的** —— 它默认了"写"就等于"改字节"。
  本单今天已经因为同一种病栽过两次,所以量一次。

## 怎么量的

在一个空 home 上跑两遍 `ds_provision.py`(第二遍模拟"更新时又跑了一次"),
两遍之间比对整棵树每份文件的 sha256:

```
python bin/ds_provision.py --home <tmp>/home --ds-root .   # 第 1 遍 rc=0
<快照 d1>
python bin/ds_provision.py --home <tmp>/home --ds-root .   # 第 2 遍 rc=0
<快照 d2>
diff d1 d2
```

## 结果

```
第1遍 rc=0
第2遍 rc=0
文件清单(第1遍后):
  5e76caf083740c4a  .nanobot/config.json
  af36bb69a7ab24fd  .openDesign/登录口令.txt
第2遍与第1遍的差异:(无)  >>> 逐字节相同
```

⚠️ **第一版探针是坏的**:我把 `--ds-root` 传成了 `./ds`(那个目录不存在),
两遍都 rc=2、树是空的,而 diff 照样报"无差异" —— **两个空目录当然相等**。
量具坏掉时最安静,这次是靠 `rc=2` 认出来的,不是靠 diff。

## 所以

1. **design 那句「死线结构上永远绿不了」不成立** —— 同一份模板下,provisioning 是
   **字节级幂等**的,死线本来就守得住。理由要改,`/UPDATE` 的必要性不能挂在这句假话上。
2. `/UPDATE` **仍然要做**,但理由换成真的那个:**新版带的模板可能和旧版不一样**。
   那时更新期跑 provisioning 就会重写业主的 `.nanobot/config.json`,
   而那份文件里有他自己的设置。安装器是本项目最验不动的组件,让它在更新期
   **完全不碰数据根**,比让它"小心地只改几个字段"便宜得多也可证得多。
3. **这条路换来一笔新账(明账,不假装没有)**:更新时不跑 provisioning,
   那么"新版需要新配置"这件事就没人做了。查了一下最坏会怎样:
   `bin/ds_shell_core.py:1005` 的 `patch_config` 对 `OUR_MCP`
   (`design-studio` / `-organize` / `-refs`)**fail closed 且说人话**
   ——「配置里缺少 OpenDesign 自己的工具服务」。
   叠上段② 的回滚(`t17`/`e4`):新版起不来 ⇒ `/api/health` 永远不答 ⇒ 自动换回旧版。
   ⇒ **最坏结果是"更新没生效、旧版照常能用"**,不是"业主拿到一台坏机器"。
   **到期条件写死**:哪天 `config/nanobot.config.windows.jsonc` 或 `OUR_MCP` 变了,
   这笔账当场到期 —— 那一版必须先解决"配置迁移由谁做"(候选:新版启动时自己迁,
   它知道自己要什么,而且那是 python、有判据),**不许靠"让业主再手动装一次"**。
