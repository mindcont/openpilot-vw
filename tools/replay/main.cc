/*
 * openpilot 回放工具主程序
 *
 * 功能说明：
 * - 解析命令行参数配置回放选项
 * - 初始化回放系统和控制台UI
 * - 支持多种数据源和播放模式
 * - 提供丰富的过滤和控制选项
 *
 * 主要特性：
 * 1. 路由数据回放：支持本地和远程数据源
 * 2. 服务过滤：允许/阻止特定服务的消息
 * 3. 播放控制：速度调节、时间跳转、循环播放
 * 4. 相机支持：道路、驾驶员、广角相机
 * 5. 缓存管理：内存缓存和文件缓存控制
 */

#include <getopt.h>

#include <iostream>
#include <map>
#include <string>
#include <vector>

#include "common/prefix.h"
#include "tools/replay/consoleui.h"  // 控制台用户界面
#include "tools/replay/replay.h"     // 回放核心功能
#include "tools/replay/util.h"       // 工具函数

// 帮助文本：详细的命令行选项说明
const std::string helpText =
R"(Usage: replay [options] [route]
Options:
  -a, --allow        白名单：允许发送的服务列表（逗号分隔）
  -b, --block        黑名单：阻止发送的服务列表（逗号分隔）
  -c, --cache        内存中缓存 <n> 个段，默认为5
  -s, --start        从 <seconds> 秒开始播放
  -x, --playback     播放速度 <speed>
      --demo         使用演示路由而不是提供自己的路由
      --auto         从最佳可用源自动加载路由（无视频）：
                     internal, openpilotci, comma_api, car_segments, testing_closet
  -d, --data_dir     包含路由的本地目录
  -p, --prefix       设置 OPENPILOT_PREFIX
      --dcam         加载驾驶员相机
      --ecam         加载广角道路相机
      --no-loop      在路由结束时停止（不循环）
      --no-cache     关闭本地缓存
      --qcam         加载qcamera
      --no-hw-decoder 禁用硬件视频解码
      --no-vipc      不输出视频
      --all          输出所有消息，包括 bookmarkButton, uiDebug, userBookmark
  -h, --help         显示此帮助信息
)";

// 回放配置结构体：存储所有命令行参数和配置选项
struct ReplayConfig {
  std::string route;                    // 路由名称或路径
  std::vector<std::string> allow;       // 允许的服务白名单
  std::vector<std::string> block;       // 阻止的服务黑名单
  std::string data_dir;                 // 本地数据目录
  std::string prefix;                   // openpilot前缀路径
  uint32_t flags = REPLAY_FLAG_NONE;    // 回放标志位
  bool auto_source = false;             // 是否自动选择数据源
  int start_seconds = 0;                // 开始播放的秒数
  int cache_segments = -1;              // 缓存段数（-1表示使用默认值）
  float playback_speed = -1;            // 播放速度（-1表示使用默认值）
};

// 解析命令行参数
bool parseArgs(int argc, char *argv[], ReplayConfig &config) {
  // 定义长选项结构体数组
  const struct option cli_options[] = {
      {"allow", required_argument, nullptr, 'a'},           // 允许服务列表
      {"block", required_argument, nullptr, 'b'},           // 阻止服务列表
      {"cache", required_argument, nullptr, 'c'},           // 缓存段数
      {"start", required_argument, nullptr, 's'},           // 开始时间
      {"playback", required_argument, nullptr, 'x'},        // 播放速度
      {"demo", no_argument, nullptr, 0},                    // 演示模式
      {"auto", no_argument, nullptr, 0},                    // 自动数据源
      {"data_dir", required_argument, nullptr, 'd'},        // 数据目录
      {"prefix", required_argument, nullptr, 'p'},          // 前缀路径
      {"dcam", no_argument, nullptr, 0},                    // 驾驶员相机
      {"ecam", no_argument, nullptr, 0},                    // 广角相机
      {"no-loop", no_argument, nullptr, 0},                 // 禁用循环
      {"no-cache", no_argument, nullptr, 0},                // 禁用缓存
      {"qcam", no_argument, nullptr, 0},                    // qcamera
      {"no-hw-decoder", no_argument, nullptr, 0},           // 禁用硬件解码
      {"no-vipc", no_argument, nullptr, 0},                 // 禁用视频输出
      {"all", no_argument, nullptr, 0},                     // 输出所有消息
      {"help", no_argument, nullptr, 'h'},                  // 帮助信息
      {nullptr, 0, nullptr, 0},  // 终止条目
  };

  // 选项名称到标志位的映射表
  const std::map<std::string, REPLAY_FLAGS> flag_map = {
      {"dcam", REPLAY_FLAG_DCAM},                    // 启用驾驶员相机
      {"ecam", REPLAY_FLAG_ECAM},                    // 启用广角相机
      {"no-loop", REPLAY_FLAG_NO_LOOP},              // 禁用循环播放
      {"no-cache", REPLAY_FLAG_NO_FILE_CACHE},       // 禁用文件缓存
      {"qcam", REPLAY_FLAG_QCAMERA},                 // 启用qcamera
      {"no-hw-decoder", REPLAY_FLAG_NO_HW_DECODER},  // 禁用硬件解码
      {"no-vipc", REPLAY_FLAG_NO_VIPC},              // 禁用VisionIPC
      {"all", REPLAY_FLAG_ALL_SERVICES},             // 输出所有服务
  };

  // 如果没有参数，显示帮助信息
  if (argc == 1) {
    std::cout << helpText;
    return false;
  }

  int opt, option_index = 0;
  // 循环解析所有命令行选项
  while ((opt = getopt_long(argc, argv, "a:b:c:s:x:d:p:h", cli_options, &option_index)) != -1) {
    switch (opt) {
      case 'a': config.allow = split(optarg, ','); break;        // 解析允许服务列表
      case 'b': config.block = split(optarg, ','); break;        // 解析阻止服务列表
      case 'c': config.cache_segments = std::atoi(optarg); break; // 设置缓存段数
      case 's': config.start_seconds = std::atoi(optarg); break;  // 设置开始时间
      case 'x': config.playback_speed = std::atof(optarg); break; // 设置播放速度
      case 'd': config.data_dir = optarg; break;                 // 设置数据目录
      case 'p': config.prefix = optarg; break;                   // 设置前缀路径
      case 0: {  // 处理长选项（没有短选项对应的）
        std::string name = cli_options[option_index].name;
        if (name == "demo") config.route = DEMO_ROUTE;          // 使用演示路由
        else if (name == "auto") config.auto_source = true;     // 启用自动数据源
        else config.flags |= flag_map.at(name);                 // 设置对应的标志位
        break;
      }
      case 'h': std::cout << helpText; return false;            // 显示帮助信息
      default: return false;                                     // 无效选项
    }
  }

  // 检查位置参数（路由名称）
  if (config.route.empty() && optind < argc) {
    config.route = argv[optind];  // 获取第一个位置参数作为路由名称
  }

  // 验证必需的路由参数
  if (config.route.empty()) {
    std::cerr << "No route provided. Use --help for usage information.\n";
    return false;
  }

  return true;  // 解析成功
}


// 主函数：程序入口点
int main(int argc, char *argv[]) {
#ifdef __APPLE__
  // 在macOS上，由于打开了所有socket，可能会达到默认的256个文件描述符限制
  // 因此将限制提高到1024
  util::set_file_descriptor_limit(1024);
#endif

  ReplayConfig config;  // 创建配置对象

  // 解析命令行参数
  if (!parseArgs(argc, argv, config)) {
    return 1;  // 解析失败，退出程序
  }

  // 如果指定了前缀路径，设置openpilot前缀
  std::unique_ptr<OpenpilotPrefix> op_prefix;
  if (!config.prefix.empty()) {
    op_prefix = std::make_unique<OpenpilotPrefix>(config.prefix);
  }

  // 创建回放对象，传入所有配置参数
  // 参数：路由名称、允许列表、阻止列表、SubMaster指针、标志位、数据目录、自动数据源
  Replay replay(config.route, config.allow, config.block, nullptr,
                config.flags, config.data_dir, config.auto_source);

  // 如果指定了缓存段数，设置段缓存限制
  if (config.cache_segments > 0) {
    replay.setSegmentCacheLimit(config.cache_segments);
  }

  // 如果指定了播放速度，设置播放速度（限制在有效范围内）
  if (config.playback_speed > 0) {
    replay.setSpeed(std::clamp(config.playback_speed,
                              ConsoleUI::speed_array.front(),  // 最小速度
                              ConsoleUI::speed_array.back())); // 最大速度
  }

  // 加载路由数据
  if (!replay.load()) {
    return 1;  // 加载失败，退出程序
  }

  // 创建控制台用户界面
  ConsoleUI console_ui(&replay);

  // 开始回放（从指定的秒数开始）
  replay.start(config.start_seconds);

  // 运行控制台UI的事件循环，返回退出代码
  return console_ui.exec();
}
