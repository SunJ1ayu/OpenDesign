#!/usr/bin/env python3
"""生成 OpenDesign 的图标 —— 一份形状,两个出口。

  · `assets/图标.png`      托盘图标(`ds_shell.tray_image()` 找的就是它)
  · `installer/opendesign.ico`  启动器 exe / 快捷方式 / 安装器的图标

**为什么要有这个脚本,而不是丢两个二进制进仓**:两处图标一旦各画各的,
以后改一处就会剩下另一处 —— 本机为"同一件事复制到第二个地方、只更新其中一个"
记过好几次账。形状只写一遍,两个出口都从它生成。

形状本身不是新画的:抄的是 `bin/ds_shell.py:tray_image()` 里那个兜底图形
(深青底 + 暖黄方块),这样"包里带了图标"和"包里没带、当场画一个"看起来是同一个东西。

用法:make-icon.py [仓库根](默认为脚本上一级)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

BG = (38, 70, 83, 255)     # 深青
FG = (233, 196, 106, 255)  # 暖黄
# .ico 里放这几档:16/32 给任务栏与列表,48 给桌面,256 给大图标视图。
# 少放一档 Windows 会自己缩,缩出来的小尺寸糊得很明显。
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def draw(size: int) -> Image.Image:
    """按 64×64 的比例放大到任意尺寸画一遍(不是缩放位图,免得小尺寸糊掉)。"""
    k = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4 * k, 4 * k, 60 * k - 1, 60 * k - 1), radius=max(2, round(14 * k)), fill=BG)
    d.rounded_rectangle((18 * k, 18 * k, 46 * k - 1, 46 * k - 1), radius=max(1, round(6 * k)), fill=FG)
    return img


def main(argv: list[str]) -> int:
    repo = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parent.parent
    png = repo / "assets" / "图标.png"
    ico = repo / "installer" / "opendesign.ico"
    png.parent.mkdir(parents=True, exist_ok=True)
    ico.parent.mkdir(parents=True, exist_ok=True)

    draw(256).save(png, format="PNG", optimize=True)
    # PIL 的 ico 保存会自己按 sizes 缩放;为了小尺寸清晰,逐档自己画再塞进去。
    draw(256).save(ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                   append_images=[draw(s) for s in ICO_SIZES if s != 256])
    print(f"托盘图标 → {png}  ({png.stat().st_size} 字节)")
    print(f"程序图标 → {ico}  ({ico.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
