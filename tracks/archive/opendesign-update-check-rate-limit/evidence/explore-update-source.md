# 前提攻击:查更新换什么查法(panel-explore,2026-09-15 夜)

- brief:`/root/aiwork/tasks/opendesign-update-check-rate-limit-explore.md`
- 主 agent 方向(派发前落盘):`/root/aiwork/tasks/opendesign-update-check-rate-limit-my-direction.md` —— API 为主,失败退 atom + `.sha256` 小文件
- 日志前缀:`/root/aiwork/logs/explore-opendesign-update-check-rate-limit-20260915-225151`(submimo / subdeepseek / subglm〔glm-5.3〕/ subgrok 四份,全部 rc=0)

## 四个方向

| 腿 | 发现 | 完整性 | 签名 | 其它 |
|---|---|---|---|---|
| MiMo | `releases/latest/download/latest.json`,不行退 atom | 每版 `latest.json` | GPG | 撤回字段;自己也说 /latest 对预发布可能 404 |
| DeepSeek | **atom 为主**、raw 指针为备、API 最后 | 每版 `update-manifest.json` | Ed25519 | **按版本取最大不按条目先后**;ETag;负缓存退避;revoked/min_supported |
| GLM-5.3 | **atom 为主**、API 为备 | 每版 `update.json` | minisign 主备两把 | ETag;启动那次绕过缓存;发版脚本校验清单;断点续传;杀软 |
| Grok | atom | 说"digest 从 JSON 拿"—— **atom 里没有 digest,这条讲不通** | 无 | 浅 |

## 综合(不是投票,逐条给理由)

- **改**:主次反过来 —— atom 为主、API 为备。理由:以后每次打开都查,共用出口上 API 多半已被限流;DeepSeek/GLM/Grok 三家同向。
- **改**:`.sha256` 小文件 → 清单 JSON(带 tag / version / name / size / sha256 / notes,可交叉核对)。MiMo/DeepSeek/GLM 三家同向。
- **采纳**:按版本号取最大(DeepSeek、GLM 各自点出 atom 按时间排)。
- **不做**:清单签名 —— 理由见 design 风险 2(治的是可用性;私钥与 gh 凭证同机;丢钥匙即断更)。
- **挪到自动更新那单**:撤回 / 最低支持版本、启动时绕过缓存与退避。
- **未实证的承重假设**(DeepSeek、GLM 都点了):共用 VPN 出口上 atom 是否另有限流。我只在干净 IP 上连打 70 次 = 70×200。⇒ 保留 API 备路 + 界面显示原因。
