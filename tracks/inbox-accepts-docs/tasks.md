# Tasks: inbox-accepts-docs

- base-ref: 222f906

- [x] 判据先行(实现前红)—— `c4c9d09`
- [x] 实现 + 版本 0.79.0 —— `2ef544e`;端到端正面判据(拖真 PDF/DWG ⇒ 落盘且界面看得见)
- [x] full 四审 → **subdeepseek BLOCK**,五条逐条核实为真,已全修 + 判据补强
- [x] 顺带上了一道机械闸:`tests/run-all.sh` 第④段 **dist 新鲜度**
      (今天两次被入库产物咬,第二次是我改完文案没 build)
- [x] 仓库级总跑:node 342 / python 879 / MCP 闸 / dist 新鲜度 / e2e 32 PASS 0 FAIL 2 SKIP
- [ ] **真机验收**(只有机主能做):把一张真图纸(dwg)和一份真 PDF 拖进收件箱卡,
      看落盘 + 卡片上看得见 + 「扫描整理」认得出类目(PDF→01-资料 自动,DWG→03-CAD 要你确认)
