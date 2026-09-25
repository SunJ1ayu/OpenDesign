// 5b 技能页(track p4 T5,handoff §8)。design D5:卡片 = 真实能力的静态清单
// (不放 CAD 转 3D 等未接入的假卡——点了没反应=欺骗用户);点卡 → 3a 新对话
// 预填调用话术(复用 P2 prefill 钩子)。「+ 添加技能」本轮无行为。

// 技能表只有一份(track opendesign-composer-zcode):「+」菜单与打 / 弹出的表用的也是它。
import { SKILLS } from "./chat/composerSkills.ts";

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
