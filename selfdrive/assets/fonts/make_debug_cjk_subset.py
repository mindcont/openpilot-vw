#!/usr/bin/env python3
"""
生成 CAN 调试面板用的中文字体子集(WenQuanYi Micro Hei 精简版)。

openpilot 自带的 unifont 是 16px 点阵字体,渲染中文样式较差;而完整 CJK 字体
有若干 MB,不适合入库。这里从系统 WenQuanYi Micro Hei 中抽取调试面板实际用到的
汉字 + 常用车辆/状态术语,先生成一个几十 KB 的子集 TTF,再用 openpilot 自带的
process.py 把它烘焙成 BMFont(.fnt + .png 图集),随仓库分发,可移植到 Orin NX
/ comma 3X 等目标设备。

关键点:
1. 必须用 TrueType(glyf)轮廓的字体做源,不能用 Noto Sans CJK(CFF/PostScript
   轮廓)——raylib 的 stb_truetype 光栅化 CFF 会得到空白字形。WenQuanYi Micro Hei
   与 openpilot 自带 Inter 一样是 glyf 轮廓。
2. 运行时用 rl.load_font 加载 .fnt(BMFont),而非 rl.load_font_ex 直接读 TTF——
   后者在本项目 raylib 5.5 上会错乱 glyph 映射,只渲染出部分汉字。

用法(源字体在系统里时,从仓库根目录执行):
  python3 selfdrive/assets/fonts/make_debug_cjk_subset.py
产物:selfdrive/assets/fonts/WenQuanYiMicroHei-Debug.{ttf,fnt,png}
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

import process

FONT_DIR = Path(__file__).resolve().parent
SRC_TTC = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
SRC_FONT_NUMBER = 0  # WenQuanYi Micro Hei(非 Mono)
OUT = FONT_DIR / "WenQuanYiMicroHei-Debug.ttf"

# 面板用字集中定义在 process.py(构建时的唯一真源),此处复用以保证子集 TTF 与
# 构建烘焙的 .fnt 字形一致。
CHARS = set(process.DEBUG_CJK_CHARS) | set(chr(c) for c in range(32, 127))


def main() -> int:
  text = "".join(sorted(CHARS))
  font = TTFont(SRC_TTC, fontNumber=SRC_FONT_NUMBER)

  options = subset.Options()
  options.name_IDs = ["*"]
  options.recalc_bounds = True
  options.drop_tables = []
  subsetter = subset.Subsetter(options=options)
  subsetter.populate(text=text)
  subsetter.subset(font)

  # 重命名,避免与系统字体冲突
  for rec in font["name"].names:
    if rec.nameID in (1, 4, 6, 16):
      rec.string = "WenQuanYiMicroHei-Debug"

  font.save(OUT.as_posix())
  print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(CHARS)} glyphs)")

  # 烘焙成 BMFont(.fnt + .png),运行时用 rl.load_font 加载
  codepoints = tuple(sorted(ord(c) for c in CHARS))
  process._process_font(OUT, codepoints)
  fnt = OUT.with_suffix(".fnt")
  print(f"baked {fnt} ({fnt.stat().st_size // 1024} KB) + {OUT.stem}.png")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
