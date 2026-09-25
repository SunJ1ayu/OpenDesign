# Design: opendesign-release-09813

- Change: opendesign-release-09813
- Status: settled

## Goal-to-design check

- 当前行为 → 拟改变的行为:业主两台机器跑 0.98.12(存 key 后连不上);发布 0.98.13 后,打开软件出现「重启以更新」,点了装上新版。
- 检查深度:沿用已验证的发布契约(installer/RELEASE.md,0.98.9~0.98.12 四次走通),只换版本号与说明 ⇒ 轻量;premise_attack not_required。
- 完全照做仍可能失败:① 云跑绿、生产源资产与被测不一致 ⇒ 生产源 smoke 比字节;② 说明让业主做错事 ⇒ QA 两家以业主视角看。

## Approach

照 `installer/RELEASE.md`:云 `electron-e2e` 整跑 FAIL 0 → 取三样 → `release-feed.mjs verify / rewrite / verify` → `gh release create`(正式版)→ 换中文说明 → 生产源 smoke。

## Test strategy (oracle)

- 本地 run-all(final)+ 云 Windows electron-e2e(E1~E7,含被测版上的更新链)FAIL 0。
- 生产源 smoke:正式版、三样取回 200、latest 清单版本 = 0.98.13、字节 = artifact、latest.yml 对得上安装包、旧 blockmap 在、tag 源码 = 被测提交(只差 tracks/)。
- **能被什么骗过**:云上的更新链测的是「0.98.13 → 替身 0.98.14」,真 0.98.12 → 0.98.13 这一跳用的是 0.98.12 里的更新器(0.98.11→12 已同形走通);业主真机回显补这一环。
