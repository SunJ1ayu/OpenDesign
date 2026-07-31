# Design: opendesign-button-roles

- Change: opendesign-button-roles
- Status: draft

> 不是开放架构分叉(方向只有一个:换成既有的角色 class)。**不花 panel-explore。**

## Approach

纯替换,九个使用点:

| 位置 | 现在 | 换成 |
|---|---|---|
| `chat/ChatPage.tsx:666,669`(重试 / 退出登录) | `chat-btn` | `btn-secondary` |
| `workspace/CompanionColumn.tsx:343` | `chat-btn` | `btn-secondary` |
| `workspace/CompanionColumn.tsx:336,373` | `chat-btn primary` | `btn-primary` |
| `workspace/InboxCard.tsx:101,277` | `chat-btn primary` | `btn-primary` |
| `TodoPage.tsx:667`(去项目) | `go-link` | `link-act` |
| `TodoRail.tsx:208`(展开对话) | `rail-expand-link` | `link-act` |

`app.css` 删掉 `.chat-btn` / `.chat-btn.primary` / `.go-link` / `.rail-expand-link`
四条规则(及其 `:hover`),原地留注释写明为什么消失。

## Key trade-offs / risks

**已知会有观感变化,是刻意接受的**(收敛的代价,不是 bug):

1. `.chat-btn` 12.5px → `.btn-secondary` 11.5px:**字号小 1px**。
2. `.chat-btn.primary` → `.btn-primary`:**高 30px、字重 600、padding 0 16**(原来无高度约束)。

**两个真陷阱 —— 光换 class 会坏,判据必须接住:**

3. `.go-link` 比 `.link-act` 多一条 **`flex: none`**。它长在待办项目卡的卡头 flex 行里,
   丢了这条会被压缩 → 「去项目」换行或被挤没。
4. `.rail-expand-link` 比 `.link-act` 多一条 **`align-self: flex-start`**。它长在右栏的
   flex 纵列里,丢了这条会被拉伸成整行宽。
5. **写静态判据时当场抓到的、我 design 第一版漏了的第三条**:
   `app.css:1104` 还有一条**上下文规则** `.rail-ask-head .rail-expand-link { margin-left: auto; }`
   —— 「展开对话」是靠它被推到标题行右端的。只改 tsx 里的 class 名、不管这条,
   它会跳回标题旁边。**判据必须钉"它贴着标题行右端"**,否则这条丢了没人知道。
   > 记账:**这是判据倒逼出的规格补全**,不是执行腿的锅 —— 派活前就该写全。
   > 同一条教训在 T3 出现过(「选中即展开」是写判据时才发现设计错的)。

> ⚠️ **3、4 不写进任务书**。它们正是"照着红的考卷把实现写绿"该由判据抓的东西;
> 提前告诉执行腿等于替它做了判断,也就验不出这一档腿的真实返工率
> —— 而**这一单的第二目的就是给 [[model-tiering-trial]] 补一个返工率样本**。

## Alternatives considered

- **顺手把 `.connect-workspace` 也收了** —— 没选。它是描边赤陶,**第三种视觉**;
  "要不要有这一档"是规格问题,混进清理单里就等于偷偷做了个设计决定。
- **一并重画三档的长相** —— 没选。用户两次的具体指令都是「统一」「都用一样的」,
  没说要换样子;收敛之后要重画随时可以,反过来不行。
- **只改 `.chat-btn`,两个 link 留着** —— 没选。留一个就等于这条反馈线还会再来一轮。

## Test strategy (oracle)

**两份,一静一动,缺一不可:**

1. **`tests/test_button_roles.mjs`(静态,总覆盖)**:扫 `web/src` 全部源文件,
   三个一次性 class 名的出现次数必须为 **0**(tsx 与 css 都算)。
   **作用:防"只改了看得见的那几处"** —— 九个点里有三个(整理方案的确认/跳过)
   要很重的夹具才走得到,行为判据到不了,静态扫描到得了。

2. **`tests/e2e/button_roles.e2e.mjs`(行为 + 观感)**:真 chromium + 真 ds_web。
   - 走过的每条路由上,三个一次性 class 渲染出来的元素数必须为 0;
   - **同一角色 class 的按钮,computed 外观必须完全一致**(高/边框/圆角/底色/字号/字重/颜色)
     —— 这是"规范落地"唯一可验的形式;
   - **陷阱 3**:「去项目」不许被压缩(实际宽度 ≥ 内容宽度,且不换行);
   - **陷阱 4**:「展开对话」不许被拉伸(宽度明显小于它所在的列);
   - 每个按钮 `scrollWidth ≤ clientWidth`(文字没被裁掉)、页面无横向溢出。

### 这个 oracle 能被什么骗过?

- **"全绿但更难看"**:我钉的是**一致性**,不是**好看**。九个点全统一成同一档,
  完全可能整体比现在丑(比如聊天区那两个按钮变小 1px 后在深色卡片上显得虚)。
  **一致性断言对此永远是绿的。** ⇒ **必须截图,而且要截到聊天区和整理方案两处**,
  不能只截好截的。史料:07-24 `columnCount==="3"` 全绿而正文被压成竖排。
- **"角色分错但一致"**:如果执行腿把某个主动作降成了 `.link-act`,组内一致性照样绿。
  ⇒ 判据里对 **9 个点逐点钉死目标角色**(见上表),不只钉"组内一致"。
- **走不到的路由**:整理方案那三个点(CompanionColumn 336/343/373)行为判据到不了,
  只有静态扫描兜着。**静态扫描证明"class 名没了",证明不了"换对了"** ——
  这三点的正确性靠闸③(我亲读 diff)+ 截图,记进 verify 的已知缺口。
