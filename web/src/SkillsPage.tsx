// 5b 技能页(track p4 T5,handoff §8)。design D5:卡片 = 真实能力的静态清单
// (不放 CAD 转 3D 等未接入的假卡——点了没反应=欺骗用户);点卡 → 3a 新对话
// 预填调用话术(复用 P2 prefill 钩子)。「+ 添加技能」本轮无行为。

type Skill = {
  abbr: string; // 图标块缩写
  name: string;
  desc: string;
  flow: string; // 输入 → 输出 角标
  prefill: string;
};

const SKILLS: Skill[] = [
  {
    abbr: "记",
    name: "记一下",
    desc: "把业主的口头改动记进项目变更账本,自动编号、永不丢。",
    flow: "口头 → 变更记录",
    prefill: "记一下:",
  },
  {
    abbr: "理",
    name: "整理文件夹",
    desc: "扫描一个目录给出归类方案,你确认之后才动文件。",
    flow: "扫描 → 方案 → 确认",
    prefill: "帮我扫描整理这个文件夹:",
  },
  {
    abbr: "图",
    name: "找参考图",
    desc: "按空间、风格在已入库的参考图里精确检索。",
    flow: "空间/风格 → 图",
    prefill: "找参考图:",
  },
];

type Props = { onUseSkill: (prefill: string) => void };

export default function SkillsPage({ onUseSkill }: Props) {
  return (
    <div className="page skills-page">
      <header className="todo-head">
        <h2 className="serif">技能</h2>
        <span className="sub">在对话里随时调用,也可以从这里直接开始</span>
      </header>
      <div className="skill-grid">
        {SKILLS.map((s) => (
          <button className="skill-card" key={s.name} onClick={() => onUseSkill(s.prefill)}>
            <span className="icon-block">{s.abbr}</span>
            <span className="nm">{s.name}</span>
            <span className="ds">{s.desc}</span>
            <span className="flow mono">{s.flow}</span>
          </button>
        ))}
        <div className="skill-card add" title="接入新技能后在这里出现(CAD 转 3D 等排期中)">
          <span className="plus">+</span>
          <span className="ds">添加技能</span>
        </div>
      </div>
      <p className="muted tip">提示:在任何对话里直接说事,AI 会自己挑工具;这页只是快捷入口。</p>
    </div>
  );
}
