"""
CAN 调试叠加面板：在 onroad 画面左上角叠加显示 CAN 总线关键变量，方便实车调试。
通过环境变量 CAN_DEBUG=1 启用（见 AugmentedRoadView 集成）。

数据来自 ui_state.sm（已订阅 carState/carControl/pandaStates 等），
读取的是 CarState（由 vw_mqb.dbc 解析的车辆信号）。
"""
import pyray as rl
from cereal import log
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.widgets import Widget

GearShifter = log.CarState.GearShifter

# 面板样式（逻辑坐标系，2160×1080；MID_UI 会等比缩放）
PANEL_X = 40
PANEL_Y = 40
PANEL_W = 620
ROW_H = 46
FONT_SIZE = 34
PAD = 24

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
    rows = []

    # --- 车辆信号(CarState,来自 CAN 解析)---
    rows.append(("车速 vEgo", f"{cs.vEgo * 3.6:5.1f} km/h", VALUE))
    rows.append(("仪表车速", f"{cs.vEgoCluster * 3.6:5.1f} km/h", VALUE))
    rows.append(("方向盘角度", f"{cs.steeringAngleDeg:6.1f} deg", VALUE))
    rows.append(("方向盘力矩", f"{cs.steeringTorque:5.1f}", VALUE))
    rows.append(("档位", self._gear_name(cs.gearShifter), VALUE))
    rows.append(("油门/刹车", f"{cs.gas:.2f} / {cs.brake:.2f}", VALUE))
    rows.append(("踏板 gas/brk", f"{int(cs.gasPressed)} / {int(cs.brakePressed)}", VALUE))
    rows.append(("静止 standstill", "YES" if cs.standstill else "no", VALUE))
    rows.append(("转向灯 L/R", f"{int(cs.leftBlinker)} / {int(cs.rightBlinker)}", VALUE))
    rows.append(("巡航 en/spd",
                 f"{int(cs.cruiseState.enabled)} / {cs.cruiseState.speed * 3.6:.0f}", VALUE))
    rows.append(("转向可用/退避",
                 f"{int(not cs.steerFaultTemporary)} / {int(cs.steeringPressed)}", VALUE))
    rows.append(("latActive", "YES" if cc.latActive else "no", VALUE))

    return rows

  def _render(self, rect: rl.Rectangle):
    sm = ui_state.sm
    rows = self._rows()

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
    rl.draw_text_ex(self._font_bold, "CAN DEBUG", rl.Vector2(tx, ty), FONT_SIZE + 4, 0, TITLE)
    ty += ROW_H

    # 车辆信号
    for label, value, color in rows:
      rl.draw_text_ex(self._font, label, rl.Vector2(tx, ty), FONT_SIZE, 0, LABEL)
      vw = rl.measure_text_ex(self._font_bold, value, FONT_SIZE, 0).x
      rl.draw_text_ex(self._font_bold, value, rl.Vector2(x + PANEL_W - PAD - vw, ty), FONT_SIZE, 0, color)
      ty += ROW_H

    # 分隔线
    ty += ROW_H // 2
    rl.draw_line_ex(rl.Vector2(tx, ty), rl.Vector2(x + PANEL_W - PAD, ty), 1, LABEL)
    ty += ROW_H // 2

    # 消息健康
    rl.draw_text_ex(self._font_bold, "消息 alive / valid", rl.Vector2(tx, ty), FONT_SIZE, 0, TITLE)
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
