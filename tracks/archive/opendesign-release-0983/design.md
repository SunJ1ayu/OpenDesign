# design: 发 0.98.3

## 唯一的设计判断:版本号来源不许有第二份

`installer/build-installer.sh:47` 用 `grep -oP '^VERSION = "\K[^"]+' bin/ds_web.py`
读版本,**只读不写**,读不出就 `die`。所以 bump 只改那一处,不许在 .nsi、
workflow、release 说明里再写死一份 —— 那是"把事实复制到第二个地方,只更新其中一个"
那个反复栽的坑。

**例外(且必须显式)**:`.github/workflows/windows-package-probe.yml` 的
`workflow_dispatch` 默认值**结构上无法从仓库读**(GitHub Actions 的 `default:`
只吃字面量)。所以它天生是第二份、天生会过期 —— 这不是能修好的重复,只能
**在每次发版时同步**。本单的做法:改成 0.98.3,并把"发版时必须改这里"从注释
升级成 proposal 里的一条任务(注释已有,但注释拦不住人)。

## 不做什么

- 不改任何行为代码(那刀已归档)。
- 不动 1.0:版本号只加第三位,业主拍板才有 1.0。
- 不自动发 release 到 latest:沿用 pre-release,和前几版一致。
