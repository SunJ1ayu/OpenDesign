// 聊天输入框占位符(设计定案 P2:提示语统一)。
// 第一性:后缀「,或「记一下…」」是唯一不变量,只写一次;三个入口(首页 / 项目助手 /
// 待办右栏)各自只提供前半句「场景」,杜绝三处措辞与标点再次漂移。
// 标点严格沿用现有约定:半角逗号 U+002C、省略号 U+2026、直角引号 U+300C/300D。
export const RECORD_SUFFIX = ",或「记一下…」";

export const inputPlaceholder = (scene: string): string => `${scene}${RECORD_SUFFIX}`;
