"""
CAN 调试叠加面板：在 onroad 画面左上角叠加显示 CAN 总线关键变量，方便实车调试。
通过环境变量 CAN_DEBUG=1 启用（见 AugmentedRoadView 集成）。

数据来自 ui_state.sm（已订阅 carState/carControl/pandaStates 等），
读取的是 CarState（由 vw_mqb.dbc 解析的车辆信号）。

中文标签使用随仓库分发的 Noto Sans CJK SC 子集字体（NotoSansCJKsc-Debug.ttf，
见 make_debug_cjk_subset.py）。openpilot 自带 Inter 缺大部分 CJK 字形、unifont 为
点阵样式，故单独加载子集字体；若加载失败则自动回退到英文标签。
"""
import os
import pyray as rl
from openpilot.common.basedir import BASEDIR
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.widgets import Widget

# 面板样式（逻辑坐标系，2160×1080；MID_UI 会等比缩放）
PANEL_X = 40
PANEL_Y = 40
PANEL_W = 620
ROW_H = 46
FONT_SIZE = 34
PAD = 24

# 中文字体:预烘焙的 BMFont(.fnt + .png 图集,见 make_debug_cjk_subset.py)
# 用 rl.load_font 加载,glyph 映射由 .fnt 文件显式给出,规避 load_font_ex 运行时
# 光栅化 CJK 的缺陷(该路径会错乱字形映射,只渲染出部分汉字)。
CJK_FONT_PATH = os.path.join(BASEDIR, "selfdrive/assets/fonts/WenQuanYiMicroHei-Debug.fnt")

BG = rl.Color(0, 0, 0, 180)
LABEL = rl.Color(170, 170, 170, 255)
VALUE = rl.Color(255, 255, 255, 255)
GOOD = rl.Color(51, 204, 51, 255)
BAD = rl.Color(220, 60, 60, 255)
TITLE = rl.Color(0, 150, 255, 255)

# 关键消息健康检查列表
HEALTH_MSGS = ["carState", "modelV2", "liveCalibration", "pandaStates", "carControl"]


class CanDebugOverlay(Widget):
  def __init__(self):
    super().__init__()
    self._font = gui_app.font(FontWeight.NORMAL)
    self._font_bold = gui_app.font(FontWeight.BOLD)
    self._font_cjk = self._load_cjk_font()
    self._zh = self._font_cjk is not None

  @staticmethod
  def _load_cjk_font():
    """加载预烘焙的中文 BMFont;失败返回 None(回退英文标签)。"""
    if not os.path.exists(CJK_FONT_PATH):
      return None
    try:
      font = rl.load_font(CJK_FONT_PATH)
      if font.texture.id == 0 or font.glyphCount <= 0:
        return None
      rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
      return font
    except Exception:
      return None

  def _L(self, zh: str, en: str) -> str:
    """按字体可用性选择中/英文标签。"""
    return zh if self._zh else en

  @property
  def _label_font(self):
    return self._font_cjk if self._zh else self._font

  @staticmethod
  def _gear_name(g) -> str:
    try:
      return str(g).split(".")[-1]
    except Exception:
      return "?"

  def _rows(self):
    """返回 (标签, 值, 值颜色) 列表"""
    sm = ui_state.sm
    cs = sm["carState"]
    cc = sm["carControl"]
    L = self._L
    rows = []

    # --- 车辆信号(CarState,来自 CAN 解析) ---
    rows.append((L("车速", "Speed"), f"{cs.vEgo * 3.6:5.1f} km/h", VALUE))
    rows.append((L("仪表车速", "Cluster Spd"), f"{cs.vEgoCluster * 3.6:5.1f} km/h", VALUE))
    rows.append((L("方向盘角度", "Steer Angle"), f"{cs.steeringAngleDeg:6.1f} deg", VALUE))
    rows.append((L("方向盘力矩", "Steer Torque"), f"{cs.steeringTorque:5.1f}", VALUE))
    rows.append((L("档位", "Gear"), self._gear_name(cs.gearShifter), VALUE))
    rows.append((L("刹车", "Brake"), f"{cs.brake:.2f}", VALUE))
    rows.append((L("踏板 油门/刹车", "Pedal gas/brk"),
                 f"{int(cs.gasPressed)} / {int(cs.brakePressed)}", VALUE))
    rows.append((L("静止", "Standstill"), "YES" if cs.standstill else "no", VALUE))
    rows.append((L("转向灯 左/右", "Blinker L/R"),
                 f"{int(cs.leftBlinker)} / {int(cs.rightBlinker)}", VALUE))
    rows.append((L("巡航 使能/车速", "Cruise en/spd"),
                 f"{int(cs.cruiseState.enabled)} / {cs.cruiseState.speed * 3.6:.0f}", VALUE))
    rows.append((L("转向可用/退避", "Steer OK/Press"),
                 f"{int(not cs.steerFaultTemporary)} / {int(cs.steeringPressed)}", VALUE))
    rows.append(("latActive", "YES" if cc.latActive else "no", VALUE))

    return rows

  def _render(self, rect: rl.Rectangle):
    sm = ui_state.sm
    rows = self._rows()
    label_font = self._label_font

    n_signal = len(rows)
    n_health = len(HEALTH_MSGS)
    # 面板高度：标题 + 信号行 + 分隔 + 健康标题 + 健康行
    total_rows = 1 + n_signal + 1 + 1 + n_health
    panel_h = PAD * 2 + total_rows * ROW_H

    x = rect.x + PANEL_X
    y = rect.y + PANEL_Y
    rl.draw_rectangle_rounded(rl.Rectangle(x, y, PANEL_W, panel_h), 0.04, 10, BG)

    tx = x + PAD
    ty = y + PAD

    # 标题
    title = self._L("CAN 调试", "CAN DEBUG")
    rl.draw_text_ex(label_font, title, rl.Vector2(tx, ty), FONT_SIZE + 4, 0, TITLE)
    ty += ROW_H

    # 车辆信号
    for label, value, color in rows:
      rl.draw_text_ex(label_font, label, rl.Vector2(tx, ty), FONT_SIZE, 0, LABEL)
      vw = rl.measure_text_ex(self._font_bold, value, FONT_SIZE, 0).x
      rl.draw_text_ex(self._font_bold, value, rl.Vector2(x + PANEL_W - PAD - vw, ty), FONT_SIZE, 0, color)
      ty += ROW_H

    # 分隔线
    ty += ROW_H // 2
    rl.draw_line_ex(rl.Vector2(tx, ty), rl.Vector2(x + PANEL_W - PAD, ty), 1, LABEL)
    ty += ROW_H // 2

    # 消息健康
    health_title = self._L("消息 alive/valid", "Msg alive / valid")
    rl.draw_text_ex(label_font, health_title, rl.Vector2(tx, ty), FONT_SIZE, 0, TITLE)
    ty += ROW_H
    for msg in HEALTH_MSGS:
      alive = bool(sm.alive.get(msg, False)) if hasattr(sm, "alive") else False
      valid = bool(sm.valid.get(msg, False)) if hasattr(sm, "valid") else False
      rl.draw_text_ex(self._font, msg, rl.Vector2(tx, ty), FONT_SIZE, 0, LABEL)
      status = f"{'A' if alive else '-'} / {'V' if valid else '-'}"
      color = GOOD if (alive and valid) else BAD
      sw = rl.measure_text_ex(self._font_bold, status, FONT_SIZE, 0).x
      rl.draw_text_ex(self._font_bold, status, rl.Vector2(x + PANEL_W - PAD - sw, ty), FONT_SIZE, 0, color)
      ty += ROW_H
