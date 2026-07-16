# Design: opendesign-tool-audit

- 审计文档进仓 docs/(耐久);eval 脚本进 tests/evals/(不进 pytest,网络+key 依赖,
  触发条件=新工具/改 docstring/真机误路由)。
- eval 设计:工具清单从三个 MCP 文件 AST 抽 *_tool docstring(与真部署同源),
  16 条真实说法计分+1 条暗区探针;MiMo reasoning 模型要给足 max_tokens;
  假阴性/假阳性分开报;温度 0 单次调用(省额度+防抖)。
- 修复原则:eval 抓到的失配优先改 docstring(便宜、git pull 即达),不动代码行为。
