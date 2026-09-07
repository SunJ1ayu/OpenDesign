# Proposal: 瘦身之后没人问"谁成了孤儿"(installer-slim 的后续单)

- Date: 2026-09-07
- Status: open(**未开工** —— 由 opendesign-installer-slim 归档时的评审发现派生)

## 由来

`opendesign-installer-slim` 归档前补跑的两条评审腿(subglm/subkimi)交出 11 条发现。
其中两条当场修掉了(闸B 孤儿扫描恒瞎 / 两个读取器可能各说各话,见那一单的 f9e0782),
**剩下这些不是"现行错误",是"这套做法的边界"** —— 本单收着,别让它们只活在对话里。

## Goal

回答一个现在**没有任何闸在问**的问题:按显式清单删掉几个包之后,
**谁变成了没人引用的孤儿?** 以及,过度删除时判据能不能看出来。

## 装进来的发现(全部我已实测复现,不是转述)

### A. tornado 是 telegram 留下的孤儿,1.9 MB 还在业主的包里
`nanobot-ai 0.2.2` 硬依赖 `python-telegram-bot[socks,webhooks]`,`webhooks` 拉 `tornado~=6.5`。
删掉 `telegram/` 之后,**tornado 在全依赖树里再无 importer**(实测:唯一要求它的就是
python-telegram-bot,以及 APScheduler 的一个没装的 extra),而它连同 dist-info
好好地留在出货树里(实测 `opendesign-0.98.2/pkg`,1.9 MB)。
**显式清单永远删不到传递依赖,而没有任何闸回答"删完之后谁是孤儿"。**

### B. g3 丢掉了 P0 探针最值钱的那一半:对照组
`test_installer_slim.py` 的 g3 只断言 `discover_all()` **非空**。
P0 探针当初证明的是**差量**:不抹 15 个、抹掉 13 个,**正好少 feishu + telegram**。
差量没有变成常驻断言 ⇒ 往清单里加一个会让**保留功能**静默消失的名字时,
g3 照样绿(nanobot 对 ImportError 是 `except` + **debug 级**日志)。
venv 里 lark-oapi / python-telegram-bot 都装着,**对照组是跑得出来的**。

### C. 三种 dist-info 形状会穿透"子集判断"(今天清单里五个都不中招,已逐一核对)
1. **namespace 共用顶层目录** —— `rmtree(顶层)` 会把**别的发行版的文件一起删掉**,
   且它的 dist-info 也因子集成立被删 ⇒ **真误删**(唯一一条会造成真实损害的)
2. **`top_level.txt` 存在但为空** ⇒ `provided` 为空 ⇒ RECORD 兜底不执行 ⇒ 留下孤儿元数据
   (g4 只测了"没有 top_level.txt",没测"有但是空的")
3. **一个发行版同时提供被删包和保留包** ⇒ 包删一半、元数据留下

### D. `pip install --target` 留下的 console script 从来没被删过
删除只碰 `site-packages/<包>/` 和 `*.dist-info`;RECORD 里 `../` 开头的条目
(典型是 `Scripts/xxx.exe`)在算 provided 时被跳过,也从没被删。
今天这五个发行版都不装 console script,所以没有现象。

### E. 前提错了的话,业主看到的是"无声的缺席"
`feishu.enabled` 若翻成 true:通道在启动时失败,而 registry 的跳过只记 **debug 级**日志;
包里也没有任何"本构建删过哪些包"的标记,业主和支持侧无法从产物自查。
候选做法:包里落一份瘦身清单文件,或对"config 里 enabled=true 但 import 不到"的通道
在启动时给显式提示。

### F. build-package.sh:212 的注释夸大了孤儿元数据的炸点
注释说 `importlib.metadata` 会"报错报在离现场很远的地方"。实测 nanobot 0.2.2 的
`channels/registry.py` 与 `apps/cli/service.py` 对 entry point 加载都有 try/except,
且这五个包本就没有 `entry_points.txt`。机制真实、**剂量夸大** ——
将来可能被当成"不必修孤儿扫描"的理由。

## Non-goals

- **不在本单直接把 tornado 加进 SLIM_DROP** —— 那是产品改动,要先走 P0 探针
  (证明删了它 nanobot 仍起得来),和 installer-slim 当初一样的规格。
- 不做依赖闭包计算器。

## 开工前要先答的

A 到底值不值一单?1.9 MB / 约 200 个文件,相对 9,642 是零头。
**真正的收益在 B**(判据看不见过度删除)和 **C-1**(唯一会造成真实损害的形状)。
建议开工时按 B → C-1 → A 的顺序,A 可能会被判成"不值得"。
