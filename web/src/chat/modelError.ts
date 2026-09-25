// 模型 / 助手出错时给业主看的那句人话(track opendesign-chat-error-visible)。
//
// 网关出错时发的是一整句原文(没有 HTTP 状态码,见 design.md 探针):
//   厂商报错体 → `Error: {'message': …}`;网关自己连不上 / 超时 → `Error calling LLM: …`;
//   欠费 → 网关换成一句固定英文;主循环崩了 → `Sorry, I encountered an error.`。
// 实时(applyEvent)和回放(hydrateFromThread)都过这一个函数 ⇒ 切走再回来是同一句。
//
// 两条规矩(4c 挑战 Grok 提的,已核实):
//   ① 只认**整条内容**就是网关的壳 —— 固定句整句相等、前缀在行首。助手在正文里引用一句报错不算。
//   ② 只按**明确字眼**分类,认不准就落「通用」(指去「测试」,由测试接口拿到 HTTP 码再说人话)。
//      `invalid_request_error` 这个 type 什么都说明不了(模型名错、图片被拒也是它),永不作依据。
//      欠费先于 key:网关那句欠费英文里就写着 “API key”。

export interface ModelErrorNote {
  /** 给人看的中文:第一行说出了什么事,第二行说下一步去哪儿。 */
  text: string;
  /** 原文(key 形状的长串已打码),以小字附在后面备查。 */
  raw: string;
}

// nanobot 的固定句(site-packages/nanobot:agent/runner.py:59-64、agent/loop.py:1070、utils/runtime.py)
const ARREARS =
  "The AI provider rejected the request because the API key is out of quota or the account is in arrears. " +
  "Please top up / check the billing status of your API key and try again.";
const FIXED: Record<string, Kind> = {
  [ARREARS]: "quota",
  "Sorry, I encountered an error calling the AI model.": "generic",
  "Sorry, I encountered an error.": "internal",
  "I completed the tool steps but couldn't produce a final answer. Please try again or narrow the task.": "empty",
  "[Assistant reply unavailable due to model error.]": "generic",
};

type Kind =
  | "quota" | "auth" | "rate" | "tooLong" | "notFound" | "timeout" | "network" | "server"
  | "internal" | "empty" | "generic";

const TEXT: Record<Kind, string> = {
  auth:
    "这句没回上来:API Key 不对(填错、过期,或这把 key 没有这个模型的权限)。\n" +
    "到「设置 → 模型设置」找到发这句时用的那家(输入框右下角显示的是现在选的模型),重新填 key,再点模型旁的「测试」确认能用。",
  quota:
    "这句没回上来:这家的额度用完了、到了套餐用量上限,或者账户欠费。\n" +
    "去这家厂商的网站看看余额、充值或等额度重置;着急的话可以先在输入框右下角换一家模型。",
  rate: "这句没回上来:发得太频繁,厂商让等一会儿。\n稍等一两分钟再发一次。",
  tooLong: "这句没回上来:这段对话太长,超出了模型一次能读的长度。\n点「新对话」开一段新的再问。",
  notFound:
    "这句没回上来:这家找不到你选的这个模型(可能模型名不对,或这把 key 用不了它)。\n" +
    "在输入框右下角换一个模型再发。",
  timeout: "这句没回上来:等模型回复超时了。\n稍后再发一次;一直这样的话,在输入框右下角换一家模型试试。",
  network: "这句没回上来:连不上模型厂商。\n先看看电脑能不能上网,再发一次;网络正常还这样的话,稍后再试。",
  server:
    "这句没回上来:模型厂商那边出错了(不是你这边的问题)。\n" +
    "稍后再发一次;一直这样的话,在输入框右下角换一家模型。",
  internal: "这句没处理完:助手这边出了点故障。\n再发一次试试;一直这样的话,退出 OpenDesign 再打开。",
  empty: "这次助手做了几步操作,但没整理出回答。\n再发一次,或者把要求说得更具体一点。",
  // 「测试」只直连厂商发一句 hi(ds_credential.test_model):测得出这家能不能用,测不出图片被拒这类 ⇒ 不许替它许愿(QA Q1)
  generic:
    "这句没回上来:模型那边出错了。\n" +
    "再发一次试试(这句带了图的话,先去掉图再发);一直这样的话,到「设置 → 模型设置」点这家模型旁的「测试」,先确认这家还能用。",
};

// 按顺序匹配,先中先得(对小写后的原文)。每条都只放**明确**的字眼;四家真 401 原文见探针证据。
// 第三列 = 只对网关自己的壳(`Error calling …`,没有报错体)生效:厂商回了报错体就说明**连得上**,
// 不许叫人查网络(评审 R2:502「failed to establish upstream connection」是厂商那边的上游)。
const RULES: [Kind, RegExp, "gatewayOnly"?][] = [
  ["quota", /insufficient[_ ](quota|balance)|quota[_ ](exceeded|exhausted)|exceeded[_ ]current[_ ]quota|exceeded your current quota|out of (quota|credits)|arrear|billing|payment[_ ]required|credit balance|余额不足|欠费|充值|资源包|使用上限|用量上限|额度/],
  // 代理字眼先于 key:407「proxy authentication required」里的 authentication 不是 key 的事(评审 R2)
  ["network", /proxy/],
  ["auth", /invalid[_ ]api[_ ]key|incorrect api key|invalid[_ ]key\b|api key[^'"]{0,40}invalid|invalid[_ ]authentication|authentication|unauthori[sz]ed|令牌|身份验证|认证失败|鉴权|['"](code|status)['"]?:\s*['"]?40[13]\b/],
  ["rate", /rate[_ ]limit|too many requests|too_many_requests|request[_ ]limit|频率|并发|请求过多|过于频繁|['"](code|status)['"]?:\s*['"]?429\b/],
  ["tooLong", /context[_ ]length|maximum context|context window|too many tokens|prompt is too long|上下文.{0,6}(长度|超|过长)|超出.{0,10}长度/],
  ["notFound", /model[_ ]not[_ ]found|does not exist|no such model|unknown model|模型不存在/],
  ["timeout", /timed out|timeout|time out|stream stalled|超时/],
  ["network", /connection error|connecterror|connection (refused|reset|aborted)|failed to establish|name or service not known|getaddrinfo|nodename nor servname|network is unreachable|temporary failure in name resolution|\bssl\b|连接失败|无法连接/, "gatewayOnly"],
  ["server", /server[_ ]error|internal (server )?error|overloaded|service unavailable|bad gateway|服务繁忙|系统繁忙|服务器|['"](code|status)['"]?:\s*['"]?5\d\d\b/],
];

// Python 异常形状:`Error: RuntimeError: …`(runner.py:475 / :319)—— 是助手自己出错,不是厂商
const PY_EXC = /^Error: [A-Za-z_][\w.]*(Error|Exception): /;
const PREFIX = /^(Error: |Error calling LLM:|Error calling Azure OpenAI:)/;

/** 原文里 key 形状的长串打码,留末 4 位好认是哪一把。原文要给人看、可能被截图转发。
 *  形状:sk-/tp-/ak-/pk-/rk- 前缀、Bearer 后面、GLM 的 `<32 位十六进制>.<密文>`、`api_key=` / `x-api-key:` 后面(评审 R3)。 */
export function maskKeys(s: string): string {
  return s
    .replace(/\b((?:sk|tp|ak|pk|rk)-)[A-Za-z0-9_-]{4,}([A-Za-z0-9]{4})\b/g, "$1****$2")
    .replace(/\b(Bearer\s+)[A-Za-z0-9._~+/=-]{4,}([A-Za-z0-9]{4})\b/g, "$1****$2")
    .replace(/\b[0-9a-f]{32}\.[A-Za-z0-9]{4,}([A-Za-z0-9]{4})\b/gi, "****$1")
    .replace(/\b((?:x-)?api[_-]?key["']?\s*[:=]\s*["']?)[A-Za-z0-9._-]{4,}([A-Za-z0-9]{4})\b/gi, "$1****$2");
}

function kindOf(content: string): Kind | null {
  const fixed = FIXED[content];
  if (fixed) return fixed;
  if (!PREFIX.test(content)) return null;
  if (PY_EXC.test(content)) return "internal";
  const low = content.toLowerCase();
  const vendorBody = content.startsWith("Error: ");
  for (const [kind, re, only] of RULES) {
    if (only === "gatewayOnly" && vendorBody) continue;
    if (re.test(low)) return kind;
  }
  return "generic";
}

/** 这条助手消息若整条就是网关的出错壳 ⇒ 给人话 + 原文;否则 null(原样显示)。 */
export function describeModelError(content: string): ModelErrorNote | null {
  if (typeof content !== "string") return null;
  const t = content.trim();
  if (!t) return null;
  const kind = kindOf(t);
  if (!kind) return null;
  return { text: TEXT[kind], raw: maskKeys(t) };
}
