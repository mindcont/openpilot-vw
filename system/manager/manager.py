#!/usr/bin/env python3
"""
openpilot 进程管理器 - 负责启动、监控和管理所有 openpilot 子进程

主要功能：
1. 系统初始化：参数清理、版本设置、设备注册
2. 进程管理：根据条件启动/停止各个子进程
3. 状态监控：监控进程健康状态，自动重启崩溃进程
4. 消息通信：处理进程间消息传递和状态广播
"""

import datetime
import os
import signal
import sys
import time
import traceback

from cereal import log
import cereal.messaging as messaging
import openpilot.system.sentry as sentry
from openpilot.common.utils import atomic_write
from openpilot.common.params import Params, ParamKeyFlag
from openpilot.common.text_window import TextWindow
from openpilot.system.hardware import HARDWARE
from openpilot.system.manager.helpers import unblock_stdout, write_onroad_params, save_bootlog
from openpilot.system.manager.process import ensure_running
from openpilot.system.manager.process_config import managed_processes
from openpilot.system.athena.registration import register, UNREGISTERED_DONGLE_ID
from openpilot.common.swaglog import cloudlog, add_file_handler
from openpilot.system.version import get_build_metadata
from openpilot.system.hardware.hw import Paths


def manager_init() -> None:
  """管理器初始化函数 - 系统启动时的一次性初始化操作"""
  # 保存启动日志到文件
  save_bootlog()

  # 获取构建元数据（版本、Git信息等）
  build_metadata = get_build_metadata()

  # 初始化参数系统
  params = Params()
  # 清理各种启动时需要重置的参数
  params.clear_all(ParamKeyFlag.CLEAR_ON_MANAGER_START)      # 管理器启动时清理
  params.clear_all(ParamKeyFlag.CLEAR_ON_ONROAD_TRANSITION)  # 上路时清理
  params.clear_all(ParamKeyFlag.CLEAR_ON_OFFROAD_TRANSITION) # 停车时清理
  params.clear_all(ParamKeyFlag.CLEAR_ON_IGNITION_ON)        # 点火时清理
  if build_metadata.release_channel:
    params.clear_all(ParamKeyFlag.DEVELOPMENT_ONLY)          # 发布版本清理开发参数

  # 如果前置摄像头录制被锁定，则启用前置摄像头录制
  if params.get_bool("RecordFrontLock"):
    params.put_bool("RecordFront", True)

  # 为所有未设置的参数设置默认值
  for k in params.all_keys():
    default_value = params.get_default_value(k)
    if default_value is not None and params.get(k) is None:
      params.put(k, default_value)

  # 创建消息队列所需的共享内存目录
  try:
    os.mkdir(Paths.shm_path())
  except FileExistsError:
    pass  # 目录已存在，忽略
  except PermissionError:
    print(f"WARNING: failed to make {Paths.shm_path()}")

  # 设置系统版本和构建信息参数
  serial = HARDWARE.get_serial()
  params.put("Version", build_metadata.openpilot.version)           # openpilot版本
  params.put("GitCommit", build_metadata.openpilot.git_commit)      # Git提交哈希
  params.put("GitCommitDate", build_metadata.openpilot.git_commit_date) # Git提交日期
  params.put("GitBranch", build_metadata.channel)                  # Git分支
  params.put("GitRemote", build_metadata.openpilot.git_origin)     # Git远程仓库
  params.put_bool("IsTestedBranch", build_metadata.tested_channel) # 是否测试分支
  params.put_bool("IsReleaseBranch", build_metadata.release_channel) # 是否发布分支
  params.put("HardwareSerial", serial)                             # 硬件序列号

  # 设备注册 - 向comma.ai服务器注册设备获取dongle_id
  reg_res = register(show_spinner=True)
  if reg_res:
    dongle_id = reg_res
  else:
    raise Exception(f"Registration failed for device {serial}")

  # 设置环境变量供日志系统使用
  os.environ['DONGLE_ID'] = dongle_id  # 设备ID
  os.environ['GIT_ORIGIN'] = build_metadata.openpilot.git_normalized_origin # Git源
  os.environ['GIT_BRANCH'] = build_metadata.channel # Git分支
  os.environ['GIT_COMMIT'] = build_metadata.openpilot.git_commit # Git提交

  # 如果代码未修改，设置CLEAN标志
  if not build_metadata.openpilot.is_dirty:
    os.environ['CLEAN'] = '1'

  # 初始化错误报告系统（Sentry）
  sentry.init(sentry.SentryProject.SELFDRIVE)
  # 绑定全局日志上下文信息
  cloudlog.bind_global(dongle_id=dongle_id,
                       version=build_metadata.openpilot.version,
                       origin=build_metadata.openpilot.git_normalized_origin,
                       branch=build_metadata.channel,
                       commit=build_metadata.openpilot.git_commit,
                       dirty=build_metadata.openpilot.is_dirty,
                       device=HARDWARE.get_device_type())

  # 预导入所有进程模块以加快后续启动速度
  for p in managed_processes.values():
    p.prepare()


def manager_cleanup() -> None:
  """管理器清理函数 - 系统关闭时停止所有子进程"""
  # 向所有进程发送停止信号（非阻塞）
  for p in managed_processes.values():
    p.stop(block=False)

  # 确保所有进程都已停止（阻塞等待）
  for p in managed_processes.values():
    p.stop(block=True)

  cloudlog.info("everything is dead")


def manager_thread() -> None:
  """管理器主线程 - 负责进程监控和状态管理的主循环"""
  # 绑定日志上下文
  cloudlog.bind(daemon="manager")
  cloudlog.info("manager start")
  cloudlog.info({"environ": os.environ})

  # 显示启动信息
  print("\033[36m" + "=" * 60 + "\033[0m")
  print("\033[36m[MANAGER]\033[0m 🚀 openpilot 进程管理器启动")
  print("\033[36m" + "=" * 60 + "\033[0m")

  params = Params()

  # 构建需要忽略（不启动）的进程列表
  ignore: list[str] = []
  # 如果设备未注册，忽略云服务相关进程
  if params.get("DongleId") in (None, UNREGISTERED_DONGLE_ID):
    ignore += ["manage_athenad", "uploader"]
    print("\033[33m[MANAGER]\033[0m ⚠️  设备未注册，忽略云服务: manage_athenad, uploader")
  # 如果设置了NOBOARD环境变量（无硬件模式），忽略pandad
  if os.getenv("NOBOARD") is not None:
    #ignore.append("pandad")
    print("\033[33m[MANAGER]\033[0m 💻 PC模式，忽略硬件进程: pandad")
  # 添加BLOCK环境变量指定的进程到忽略列表
  blocked_procs = [x for x in os.getenv("BLOCK", "").split(",") if len(x) > 0]
  ignore += blocked_procs
  if blocked_procs:
    print(f"\033[33m[MANAGER]\033[0m 🚫 手动阻止进程: {', '.join(blocked_procs)}")

  # 设置消息订阅和发布
  sm = messaging.SubMaster(['deviceState', 'carParams', 'pandaStates'], poll='deviceState')
  pm = messaging.PubMaster(['managerState'])

  print("\033[34m[MANAGER]\033[0m 📋 初始化阶段 - 启动基础进程")

  # 检查摄像头配置
  webcam_enabled = os.getenv("USE_WEBCAM") is not None
  driver_view_enabled = params.get_bool("IsDriverViewEnabled")
  if webcam_enabled:
    if driver_view_enabled:
      print("\033[32m[MANAGER]\033[0m 📹 摄像头已启用: webcamerad 将启动 (USE_WEBCAM=1, IsDriverViewEnabled=True)")
    else:
      print("\033[33m[MANAGER]\033[0m ⚠️  摄像头配置: webcamerad 需要驾驶员视图模式或上路状态")
      print("\033[33m[MANAGER]\033[0m 💡 提示: 运行 'python3 enable_camera.py' 启用摄像头")
  else:
    print("\033[33m[MANAGER]\033[0m 📹 摄像头未启用: 设置 USE_WEBCAM=1 启用 webcamerad")

  # 初始化：设置离线参数，启动所有符合条件的进程
  write_onroad_params(False, params)  # 设置为离线状态
  ensure_running(managed_processes.values(), False, params=params, CP=sm['carParams'], not_run=ignore)

  # 状态跟踪变量
  started_prev = False    # 上一次的启动状态
  ignition_prev = False   # 上一次的点火状态

  print("\033[32m[MANAGER]\033[0m ✅ 初始化完成，进入主监控循环")
  print("\033[36m" + "=" * 60 + "\033[0m")

  # 主监控循环
  while True:
    # 更新消息，1000ms超时
    sm.update(1000)

    # 获取当前设备启动状态
    started = sm['deviceState'].started

    # 检测状态变化并清理相应参数
    if started and not started_prev:
      # 从离线转为在线：清理上路转换参数
      print("\033[32m[MANAGER]\033[0m 🚗 车辆上路 - 启动驾驶相关进程")
      params.clear_all(ParamKeyFlag.CLEAR_ON_ONROAD_TRANSITION)
    elif not started and started_prev:
      # 从在线转为离线：清理下路转换参数
      print("\033[33m[MANAGER]\033[0m 🏠 车辆停车 - 停止驾驶相关进程")
      params.clear_all(ParamKeyFlag.CLEAR_ON_OFFROAD_TRANSITION)

    # 检测点火状态（通过CAN或硬件线路）
    ignition = any(ps.ignitionLine or ps.ignitionCan for ps in sm['pandaStates'] if ps.pandaType != log.PandaState.PandaType.unknown)
    if ignition and not ignition_prev:
      # 点火时清理相关参数
      print("\033[32m[MANAGER]\033[0m 🔥 车辆点火 - 清理点火参数")
      params.clear_all(ParamKeyFlag.CLEAR_ON_IGNITION_ON)

    # 更新在路参数，这会驱动pandad的安全设置线程
    if started != started_prev:
      write_onroad_params(started, params)

    # 更新状态跟踪变量
    started_prev = started
    ignition_prev = ignition

    # 确保所有应该运行的进程都在运行
    ensure_running(managed_processes.values(), started, params=params, CP=sm['carParams'], not_run=ignore)

    # 生成进程状态显示字符串（绿色=运行，红色=停止）
    running = ' '.join("{}{}\u001b[0m".format("\u001b[32m" if p.proc.is_alive() else "\u001b[31m", p.name)
                       for p in managed_processes.values() if p.proc)
    print(running)          # 控制台输出
    cloudlog.debug(running) # 调试日志

    # 发布管理器状态消息
    msg = messaging.new_message('managerState', valid=True)
    msg.managerState.processes = [p.get_process_state_msg() for p in managed_processes.values()]
    pm.send('managerState', msg)

    # 更新AGNOS电源监控看门狗（防止系统休眠）
    try:
      if sm.all_checks(['deviceState']):
        with atomic_write("/var/tmp/power_watchdog", "w", overwrite=True) as f:
          f.write(str(time.monotonic()))
    except Exception:
      pass  # 忽略看门狗更新失败

    # 检查是否需要退出主循环（卸载/关机/重启）
    shutdown = False
    for param in ("DoUninstall", "DoShutdown", "DoReboot"):
      if params.get_bool(param):
        shutdown = True
        params.put("LastManagerExitReason", f"{param} {datetime.datetime.now()}")
        print(f"\033[31m[MANAGER]\033[0m 🛑 系统关闭: {param}")
        cloudlog.warning(f"Shutting down manager - {param} set")

    if shutdown:
      break


def main() -> None:
  """主函数 - 管理器的入口点"""
  # 执行初始化
  manager_init()

  # 如果设置了PREPAREONLY环境变量，只做初始化不运行主循环
  if os.getenv("PREPAREONLY") is not None:
    return

  # 设置SIGTERM信号处理器，收到终止信号时退出
  signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(1))

  try:
    # 运行主监控线程
    manager_thread()
  except Exception:
    # 打印异常信息并上报到Sentry
    traceback.print_exc()
    sentry.capture_exception()
  finally:
    # 无论如何都要清理所有进程
    manager_cleanup()

  # 根据参数执行相应的系统操作
  params = Params()
  if params.get_bool("DoUninstall"):
    cloudlog.warning("uninstalling")
    HARDWARE.uninstall()  # 卸载openpilot
  elif params.get_bool("DoReboot"):
    cloudlog.warning("reboot")
    HARDWARE.reboot()     # 重启系统
  elif params.get_bool("DoShutdown"):
    cloudlog.warning("shutdown")
    HARDWARE.shutdown()   # 关闭系统


if __name__ == "__main__":
  # 解除标准输出阻塞（确保日志能正常输出）
  unblock_stdout()

  try:
    main()
  except KeyboardInterrupt:
    # 用户按Ctrl+C退出
    print("got CTRL-C, exiting")
  except Exception:
    # 管理器启动失败的异常处理
    add_file_handler(cloudlog)  # 添加文件日志处理器
    cloudlog.exception("Manager failed to start")

    try:
      # 尝试停止UI进程（如果已启动）
      managed_processes['ui'].stop()
    except Exception:
      pass  # 忽略停止UI时的异常

    # 显示错误信息窗口（显示最后3行异常信息）
    error = traceback.format_exc(-3)
    error = "Manager failed to start\n\n" + error
    with TextWindow(error) as t:
      t.wait_for_exit()  # 等待用户关闭错误窗口

    raise  # 重新抛出异常

  # 手动退出，因为我们是被fork的进程
  sys.exit(0)
