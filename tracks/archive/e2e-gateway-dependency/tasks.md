# Tasks: e2e-gateway-dependency

- base-ref: aafd008

> 本单**没有委托**:改的是判据本身,硬规矩「oracle 永远由主 agent 亲自写,绝不外包」。

- [x] 1. 红检 A:现状在**无 gateway** 下跑两条 —— 2 FAIL(收据 `redcheck-A`)
- [x] 2. 两条 e2e 各加 `page.route` 拦 bootstrap 为 401;同步改正文件头那句「无 gateway」
- [x] 3. 绿:**无 gateway** 下两条全过
- [x] 4. 变异红检 B:连接卡 `data-ui` 改名 ⇒ 两条必须红(证明判据仍咬得动),还原回绿
- [x] 5. 绿:**有 gateway** 下两条也全过(证明不再受环境摆布)
- [x] 6. e2e 总跑一遍(默认口径,不带 --with-gateway)
- [x] 7. fast lane 两条腿(submimo/subdeepseek)+ 逐条仲裁,2 条 Low 全收并重跑绿
- [x] 8. 最终权威收据(跑在最后一次编辑 `b726b57` **之后**,rc=1 —— 红的是本机随机项,
      已用 `diag-flaky-eight` 8 PASS/0 FAIL 证伪「资源」这个舒服解释)+ 归档 `0a510b8` + 已 push
