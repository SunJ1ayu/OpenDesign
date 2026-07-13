# Tasks: opendesign-workbench-p7

- base-ref: 184857d1f99bd6a2d7e9e326ffadb5c7411f9e47

- [x] T1 ds_workspace:projectsDir 解析 + project_folders + project_dir 三级绑定;
      oracle(候选序/显式覆盖/直等/token 唯一/歧义不绑/symlink 跳过/within 闸/charset)
- [x] T2 ds_web:POST delete 针孔(CT 闸/body 读净/key 闸/_proxy 复用)+ /api/projects
      联合 + _PROJ_KEY_RE 加 #;VERSION 0.8.0;proxy/api 测试 + 405 oracle 复跑
- [x] T3 前端:apiFetch init + deleteChatSession + Sidebar ✕/未建档行 + App 删除流/
      默认选中排除未建档 + ChangesColumn 建档引导;mjs oracle;build dist
- [x] T4 e2e 真 gateway:删除流(建会话→侧栏出现→✕确认→消失)+ 未建档项目流
      (fixture 文件夹→列表出现→文件区可读→变更列引导)
- [x] T5 verify fast lane:主审先行(my-review 在 /root/aiwork/tasks/)+ submimo;
      全量回归 py+mjs;install-windows.md §5c / workspace.example.json 说明更新
