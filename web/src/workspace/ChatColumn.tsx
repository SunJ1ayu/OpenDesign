import { useState } from "react";
import ChatPage from "../chat/ChatPage";
import type { ChatSession } from "../chat/connection";

// 聊天列(handoff §4,340px):头部(项目助手 / ≡ / » 收起)+ ChatPage 真身。
// 收起(design 窄窗策略:稿上有 » 按钮)= 收成 36px 竖条,« 展开。
// P3 keep-mounted 同规矩:收起也走 CSS 隐藏,不卸载 ChatPage(卸载=丢对话)。

type Props = {
  session: ChatSession;
  prefill: { text: string; nonce: number };
  onConnected?: () => void;
  onTurnEnd?: () => void;
};

export default function ChatColumn({ session, prefill, onConnected, onTurnEnd }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className={`chatcol${collapsed ? " collapsed" : ""}`}>
      {collapsed ? (
        <div className="chat-rail">
          <button className="icon-btn" title="展开项目助手" onClick={() => setCollapsed(false)}>
            «
          </button>
        </div>
      ) : (
        <div className="chatcol-head">
          <span className="t">项目助手</span>
          <span className="grow" />
          <button className="icon-btn" title="历史对话(即将支持)">≡</button>
          <button className="icon-btn" title="收起" onClick={() => setCollapsed(true)}>
            »
          </button>
        </div>
      )}
      <div className={`chatcol-body${collapsed ? " route-hidden" : ""}`}>
        <ChatPage session={session} prefill={prefill} onConnected={onConnected} onTurnEnd={onTurnEnd} />
      </div>
    </section>
  );
}
