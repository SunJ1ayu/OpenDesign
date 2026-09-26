// 输入框里的技能表与问候语(track opendesign-composer-zcode,照 ZCode 改输入框五条)。
// 技能表**只有这一份**:技能页(SkillsPage)、「+」菜单、打 / 弹出的表都从这里取 —— 以前技能页自己写着一份 prefill,
// 输入框的「✎ 记一下」又手写一份「记一下:」,两处迟早对不上。
// 全部纯函数,node --test 直接可测(tests/test_composer_zcode.mjs)。

export type Skill = {
  abbr: string; // 图标块缩写
  name: string;
  desc: string;
  flow: string; // 输入 → 输出 角标
  prefill: string;
  /** 打 / 之后按这些字也筛得到(照 ZCode 的 keywords);名字与缩写本来就算。 */
  keywords: string[];
};

export const SKILLS: Skill[] = [
  {
    abbr: "记",
    name: "记一下",
    desc: "把业主的口头改动记进项目变更账本,自动编号、永不丢。",
    flow: "口头 → 变更记录",
    prefill: "记一下:",
    keywords: ["记账", "账本", "变更", "改动"],
  },
  {
    abbr: "理",
    name: "整理文件夹",
    desc: "扫描一个目录给出归类方案,你确认之后才动文件。",
    flow: "扫描 → 方案 → 确认",
    prefill: "帮我扫描整理这个文件夹:",
    keywords: ["整理", "文件", "扫描", "归类"],
  },
  {
    abbr: "图",
    name: "找参考图",
    desc: "按空间、风格在已入库的参考图里精确检索。",
    flow: "空间/风格 → 图",
    prefill: "找参考图:",
    keywords: ["参考", "找图", "图库"],
  },
];

/** 以 / 开头的触发符:ASCII `/`;微软拼音中文标点模式下按 / 键打出的「、」;全角「／」。
 *  ZCode 只给 `$` 做了 `¥/￥` 别名,没管「、」—— 它的用户多开英文模式,我们的业主不是(design.md P4)。 */
const SLASH = /^[/\u3001\uff0f]([^\s/\u3001\uff0f]*)$/; // / 、 ／

/** 整段草稿就是一个 / 查询 ⇒ 返回 / 后面的字(可能是空串);否则 null(不弹)。
 *  只认整段:第二行的 /、带空格的 /xxx 都当普通话。 */
export function slashQuery(draft: string): string | null {
  const m = SLASH.exec(draft);
  return m ? m[1] : null;
}

export function filterSkills(query: string): Skill[] {
  const q = query.trim().toLowerCase();
  if (!q) return SKILLS;
  return SKILLS.filter((s) =>
    [s.name, s.abbr, ...s.keywords].some((w) => w.toLowerCase().includes(q)));
}

/** 已经是某个技能开头的,换掉开头(不叠两个);业主手打的全角冒号也认。整段是 / 查询的,整段换成开头。 */
export function applySkillPrefill(draft: string, skill: Skill): string {
  if (slashQuery(draft) !== null) return skill.prefill;
  let rest = draft;
  for (const s of SKILLS) {
    const head = s.prefill.slice(0, -1); // 去掉末尾的冒号
    if (rest.startsWith(`${head}:`) || rest.startsWith(`${head}\uff1a`)) { // 半角 / 全角冒号
      rest = rest.slice(head.length + 1);
      break;
    }
  }
  return `${skill.prefill}${rest.replace(/^\s+/, "")}`;
}

// ── 问候语 ────────────────────────────────────────────────────────────────────
// 分界照 ZCode(refs/zcode-ui-src/v4/ConversationDraftEmptyState.tsx:14-36):5 / 9 / 12 / 14 / 18 / 23 点换档;
// 措辞照业主看过的对照图「下午好,今天想聊点什么?」(ZCode 原句是它自己的口吻,不照抄)。
const GREETING_BOUNDARY_HOURS = [5, 9, 12, 14, 18, 23];

export function greetingFor(date: Date): string {
  const h = date.getHours();
  if (h >= 5 && h < 9) return "早上好,今天想聊点什么?";
  if (h >= 9 && h < 12) return "上午好,今天想聊点什么?";
  if (h >= 12 && h < 14) return "中午好,今天想聊点什么?";
  if (h >= 14 && h < 18) return "下午好,今天想聊点什么?";
  if (h >= 18 && h < 23) return "晚上好,今天想聊点什么?";
  return "夜深了,还在忙吗?";
}

/** 到下一个分界点还有多少毫秒(窗口开着过了分界,问候语自己换)。 */
export function nextGreetingDelayMs(date: Date): number {
  const next = GREETING_BOUNDARY_HOURS
    .map((h) => { const d = new Date(date); d.setHours(h, 0, 0, 0); return d; })
    .find((d) => d.getTime() > date.getTime());
  const target = next ?? (() => {
    const d = new Date(date);
    d.setDate(d.getDate() + 1);
    d.setHours(GREETING_BOUNDARY_HOURS[0], 0, 0, 0);
    return d;
  })();
  return Math.max(1, target.getTime() - date.getTime());
}
