import os
import operator
import platform

from cereal import car
from openpilot.common.params import Params
from openpilot.system.hardware import PC, TICI
from openpilot.system.manager.process import PythonProcess, NativeProcess, DaemonProcess

WEBCAM = os.getenv("USE_WEBCAM") is not None

def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
  """驾驶员视图模式启动条件
  
  启动条件:
  - PC模式下USE_WEBCAM=1: 总是启动
  - started=True: 车辆上路状态
  - IsDriverViewEnabled=True: 手动启用驾驶员视图
  
  影响进程: camerad, webcamerad, soundd, dmonitoringmodeld, dmonitoringd
  """
  # PC模式下总是启用摄像头
  if os.getenv("USE_WEBCAM") and os.getenv("PC"):
    result = True
    if os.getenv("LOGPRINT") == "debug":
      print(f"\033[90m[PROCESS]\033[0m driverview: PC+WEBCAM模式 -> {result}")
    return result
  
  result = started or params.get_bool("IsDriverViewEnabled")
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m driverview: started={started}, IsDriverViewEnabled={params.get_bool('IsDriverViewEnabled')} -> {result}")
  return result

def notcar(started: bool, params: Params, CP: car.CarParams) -> bool:
  """非车辆模式启动条件 (仿真/调试模式)
  
  启动条件:
  - started=True 且 CP.notCar=True
  
  影响进程: stream_encoderd, joystickd, bridge, webrtcd, webjoystick
  """
  result = started and CP.notCar
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m notcar: started={started}, CP.notCar={CP.notCar} -> {result}")
  return result

def iscar(started: bool, params: Params, CP: car.CarParams) -> bool:
  """真实车辆模式启动条件
  
  启动条件:
  - started=True 且 CP.notCar=False
  
  影响进程: controlsd, micd, joystick
  """
  result = started and not CP.notCar
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m iscar: started={started}, CP.notCar={CP.notCar} -> {result}")
  return result

def logging(started: bool, params: Params, CP: car.CarParams) -> bool:
  """日志记录启动条件
  
  启动条件:
  - started=True 且 (CP.notCar=False 或 DisableLogging=False)
  
  影响进程: loggerd
  """
  run = (not CP.notCar) or not params.get_bool("DisableLogging")
  result = started and run
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m logging: started={started}, notCar={CP.notCar}, DisableLogging={params.get_bool('DisableLogging')} -> {result}")
  return result

def ublox_available() -> bool:
  return os.path.exists('/dev/ttyHS0') and not os.path.exists('/persist/comma/use-quectel-gps')

def ublox(started: bool, params: Params, CP: car.CarParams) -> bool:
  use_ublox = ublox_available()
  if use_ublox != params.get_bool("UbloxAvailable"):
    params.put_bool("UbloxAvailable", use_ublox)
  return started and use_ublox

def joystick(started: bool, params: Params, CP: car.CarParams) -> bool:
  """手柄模式启动条件
  
  启动条件:
  - started=True 且 JoystickDebugMode=True
  
  影响进程: joystickd, joystick
  """
  result = started and params.get_bool("JoystickDebugMode")
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m joystick: started={started}, JoystickDebugMode={params.get_bool('JoystickDebugMode')} -> {result}")
  return result

def not_joystick(started: bool, params: Params, CP: car.CarParams) -> bool:
  """非手柄模式启动条件
  
  启动条件:
  - started=True 且 JoystickDebugMode=False
  
  影响进程: controlsd
  """
  result = started and not params.get_bool("JoystickDebugMode")
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m not_joystick: started={started}, JoystickDebugMode={params.get_bool('JoystickDebugMode')} -> {result}")
  return result

def long_maneuver(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and params.get_bool("LongitudinalManeuverMode")

def not_long_maneuver(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not params.get_bool("LongitudinalManeuverMode")

def qcomgps(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not ublox_available()

def always_run(started: bool, params: Params, CP: car.CarParams) -> bool:
  """总是运行条件
  
  启动条件:
  - 无条件限制，总是返回True
  
  影响进程: logmessaged, ui, deleter, hardwared, pandad, statsd, uploader
  """
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m always_run: -> True")
  return True

def only_onroad(started: bool, params: Params, CP: car.CarParams) -> bool:
  """仅在车辆上路时运行
  
  启动条件:
  - started=True
  
  影响进程: modeld, encoderd, locationd, calibrationd, torqued, 
           selfdrived, card, paramsd, lagd, plannerd, radard, feedbackd
  """
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m only_onroad: started={started} -> {started}")
  return started

def only_offroad(started: bool, params: Params, CP: car.CarParams) -> bool:
  """仅在车辆停车时运行
  
  启动条件:
  - started=False
  
  影响进程: updated
  """
  result = not started
  if os.getenv("LOGPRINT") == "debug":
    print(f"\033[90m[PROCESS]\033[0m only_offroad: started={started} -> {result}")
  return result

def or_(*fns):
  return lambda *args: operator.or_(*(fn(*args) for fn in fns))

def and_(*fns):
  return lambda *args: operator.and_(*(fn(*args) for fn in fns))

procs = [
  DaemonProcess("manage_athenad", "system.athena.manage_athenad", "AthenadPid"),

  NativeProcess("loggerd", "system/loggerd", ["./loggerd"], logging),
  NativeProcess("encoderd", "system/loggerd", ["./encoderd"], only_onroad),
  NativeProcess("stream_encoderd", "system/loggerd", ["./encoderd", "--stream"], notcar),
  PythonProcess("logmessaged", "system.logmessaged", always_run),

  NativeProcess("camerad", "system/camerad", ["./camerad"], driverview, enabled=not WEBCAM),
  PythonProcess("webcamerad", "tools.webcam.camerad", driverview, enabled=WEBCAM),
  PythonProcess("proclogd", "system.proclogd", only_onroad, enabled=platform.system() != "Darwin"),
  PythonProcess("journald", "system.journald", only_onroad, platform.system() != "Darwin"),
  PythonProcess("micd", "system.micd", iscar),
  PythonProcess("timed", "system.timed", always_run, enabled=not PC),

  PythonProcess("modeld", "selfdrive.modeld.modeld", only_onroad),
  PythonProcess("dmonitoringmodeld", "selfdrive.modeld.dmonitoringmodeld", driverview, enabled=(WEBCAM or not PC)),

  PythonProcess("sensord", "system.sensord.sensord", only_onroad, enabled=not PC),
  PythonProcess("ui", "selfdrive.ui.ui", always_run, restart_if_crash=True),
  PythonProcess("soundd", "selfdrive.ui.soundd", driverview),
  PythonProcess("locationd", "selfdrive.locationd.locationd", only_onroad),
  NativeProcess("_pandad", "selfdrive/pandad", ["./pandad"], always_run, enabled=False),
  PythonProcess("calibrationd", "selfdrive.locationd.calibrationd", only_onroad),
  PythonProcess("torqued", "selfdrive.locationd.torqued", only_onroad),
  PythonProcess("controlsd", "selfdrive.controls.controlsd", and_(not_joystick, iscar)),
  PythonProcess("joystickd", "tools.joystick.joystickd", or_(joystick, notcar)),
  PythonProcess("selfdrived", "selfdrive.selfdrived.selfdrived", only_onroad),
  PythonProcess("card", "selfdrive.car.card", only_onroad),
  PythonProcess("deleter", "system.loggerd.deleter", always_run),
  PythonProcess("dmonitoringd", "selfdrive.monitoring.dmonitoringd", driverview, enabled=(WEBCAM or not PC)),
  PythonProcess("qcomgpsd", "system.qcomgpsd.qcomgpsd", qcomgps, enabled=TICI),
  PythonProcess("pandad", "selfdrive.pandad.pandad", always_run),
  PythonProcess("paramsd", "selfdrive.locationd.paramsd", only_onroad),
  PythonProcess("lagd", "selfdrive.locationd.lagd", only_onroad),
  PythonProcess("ubloxd", "system.ubloxd.ubloxd", ublox, enabled=TICI),
  PythonProcess("pigeond", "system.ubloxd.pigeond", ublox, enabled=TICI),
  PythonProcess("plannerd", "selfdrive.controls.plannerd", not_long_maneuver),
  PythonProcess("maneuversd", "tools.longitudinal_maneuvers.maneuversd", long_maneuver),
  PythonProcess("radard", "selfdrive.controls.radard", only_onroad),
  PythonProcess("hardwared", "system.hardware.hardwared", always_run),
  PythonProcess("tombstoned", "system.tombstoned", always_run, enabled=not PC),
  PythonProcess("updated", "system.updated.updated", only_offroad, enabled=not PC),
  PythonProcess("uploader", "system.loggerd.uploader", always_run),
  PythonProcess("statsd", "system.statsd", always_run),
  PythonProcess("feedbackd", "selfdrive.ui.feedback.feedbackd", only_onroad),

  # debug procs
  NativeProcess("bridge", "cereal/messaging", ["./bridge"], notcar),
  PythonProcess("webrtcd", "system.webrtc.webrtcd", notcar),
  PythonProcess("webjoystick", "tools.bodyteleop.web", notcar),
  PythonProcess("joystick", "tools.joystick.joystick_control", and_(joystick, iscar)),
]

managed_processes = {p.name: p for p in procs}

# 命令窗口功能
def print_help():
  """显示帮助信息"""
  print("\n=== OpenPilot Process Config 命令窗口 ===")
  print("可用命令:")
  print("  iscar          - 检查真实车辆模式状态")
  print("  driverview     - 检查驾驶员视图模式状态")
  print("  notcar         - 检查非车辆模式状态")
  print("  joystick       - 检查手柄模式状态")
  print("  logging        - 检查日志记录状态")
  print("  processes      - 显示所有进程状态")
  print("  params         - 显示关键参数")
  print("  help           - 显示此帮助")
  print("  exit/quit      - 退出命令窗口")
  print("="*45)

def show_process_status(started: bool, params: Params, CP: car.CarParams):
  """显示所有进程状态"""
  print(f"\n进程状态检查 (started={started}):")
  print("-" * 40)
  
  conditions = {
    "iscar": iscar(started, params, CP),
    "driverview": driverview(started, params, CP),
    "notcar": notcar(started, params, CP),
    "joystick": joystick(started, params, CP),
    "logging": logging(started, params, CP),
    "always_run": always_run(started, params, CP),
    "only_onroad": only_onroad(started, params, CP),
    "only_offroad": only_offroad(started, params, CP)
  }
  
  for name, status in conditions.items():
    status_str = "✓" if status else "✗"
    print(f"  {name:<15}: {status_str} {status}")

def show_params(params: Params):
  """显示关键参数"""
  print("\n关键参数状态:")
  print("-" * 30)
  
  key_params = [
    "IsDriverViewEnabled",
    "JoystickDebugMode", 
    "DisableLogging",
    "LongitudinalManeuverMode",
    "UbloxAvailable"
  ]
  
  for param in key_params:
    value = params.get_bool(param)
    print(f"  {param:<25}: {value}")
  
  # 环境变量
  print("\n环境变量:")
  env_vars = ["USE_WEBCAM", "PC", "LOGPRINT"]
  for var in env_vars:
    value = os.getenv(var, "未设置")
    print(f"  {var:<15}: {value}")

def command_window():
  """命令窗口主函数"""
  try:
    params = Params()
    # 创建默认 CarParams
    CP = car.CarParams.new_message()
    CP.notCar = os.getenv("PC") is not None
    
    # 模拟 started 状态
    started = params.get_bool("IsOnroad") if params.get("IsOnroad") else False
    
    print_help()
    
    while True:
      try:
        cmd = input("\n> ").strip().lower()
        
        if cmd in ["exit", "quit", "q"]:
          print("退出命令窗口")
          break
        elif cmd == "help" or cmd == "h":
          print_help()
        elif cmd == "iscar":
          result = iscar(started, params, CP)
          print(f"iscar() = {result}")
        elif cmd == "driverview":
          result = driverview(started, params, CP)
          print(f"driverview() = {result}")
        elif cmd == "notcar":
          result = notcar(started, params, CP)
          print(f"notcar() = {result}")
        elif cmd == "joystick":
          result = joystick(started, params, CP)
          print(f"joystick() = {result}")
        elif cmd == "logging":
          result = logging(started, params, CP)
          print(f"logging() = {result}")
        elif cmd == "processes":
          show_process_status(started, params, CP)
        elif cmd == "params":
          show_params(params)
        elif cmd == "":
          continue
        else:
          print(f"未知命令: {cmd}，输入 'help' 查看帮助")
      
      except KeyboardInterrupt:
        print("\n使用 'exit' 退出")
      except Exception as e:
        print(f"错误: {e}")
        
  except Exception as e:
    print(f"初始化失败: {e}")

if __name__ == "__main__":
  command_window()
