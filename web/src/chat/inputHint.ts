// 聊天输入框占位符(设计定案 P2:提示语统一)。
// 第一性:后缀「,或「记一下…」」是唯一不变量,只写一次;三个入口(首页 / 项目助手 /
// 待办右栏)各自只提供前半句「场景」,杜绝三处措辞与标点再次漂移。
// 标点严格沿用现有约定:半角逗号 U+002C、省略号 U+2026、直角引号 U+300C/300D。
export const RECORD_SUFFIX = ",或「记一下…」";

export const inputPlaceholder = (scene: string): string => `${scene}${RECORD_SUFFIX}`;

// 聊天输入框(track opendesign-composer-zcode):「✎ 记一下」按钮挪进「+」菜单,打 / 弹技能表 ⇒ 后缀换成这句。
// 待办小框(TodoRail 的 rail-ask)是普通输入框、没有技能表,**继续用上面那个**(4c C4:不许在那儿说假话)。
export const SKILL_SUFFIX = ";输入 / 选技能";

export const composerPlaceholder = (scene: string): string => `${scene}${SKILL_SUFFIX}`;
