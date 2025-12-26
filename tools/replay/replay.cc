#include "tools/replay/replay.h"

#include <capnp/dynamic.h>
#include <csignal>
#include "cereal/services.h"
#include "common/params.h"
#include "tools/replay/util.h"

static void interrupt_sleep_handler(int signal) {}

// Helper function to notify events with safety checks
template <typename Callback, typename... Args>
void notifyEvent(Callback &callback, Args &&...args) {
  if (callback) callback(std::forward<Args>(args)...);
}

Replay::Replay(const std::string &route, std::vector<std::string> allow, std::vector<std::string> block,
               SubMaster *sm, uint32_t flags, const std::string &data_dir, bool auto_source)
    : sm_(sm), flags_(flags), seg_mgr_(std::make_unique<SegmentManager>(route, flags, data_dir, auto_source)) {
  std::signal(SIGUSR1, interrupt_sleep_handler);

  if (!(flags_ & REPLAY_FLAG_ALL_SERVICES)) {
    block.insert(block.end(), {"bookmarkButton", "uiDebug", "userBookmark"});
  }
  setupServices(allow, block);
  setupSegmentManager(!allow.empty() || !block.empty());
}

void Replay::setupServices(const std::vector<std::string> &allow, const std::vector<std::string> &block) {
  auto event_schema = capnp::Schema::from<cereal::Event>().asStruct();
  sockets_.resize(event_schema.getUnionFields().size(), nullptr);

  std::vector<const char *> active_services;
  active_services.reserve(services.size());

  for (const auto &[name, _] : services) {
    bool is_blocked = std::find(block.begin(), block.end(), name) != block.end();
    bool is_allowed = allow.empty() || std::find(allow.begin(), allow.end(), name) != allow.end();
    if (is_allowed && !is_blocked) {
      uint16_t which = event_schema.getFieldByName(name).getProto().getDiscriminantValue();
      sockets_[which] = name.c_str();
      active_services.push_back(name.c_str());
    }
  }

  std::string services_str = join(active_services, ", ");
  rInfo("active services: %s", services_str.c_str());
  if (!sm_) {
    pm_ = std::make_unique<PubMaster>(active_services);
  }
}

void Replay::setupSegmentManager(bool has_filters) {
  seg_mgr_->setCallback([this]() { handleSegmentMerge(); });

  if (has_filters) {
    std::vector<bool> filters(sockets_.size(), false);
    for (size_t i = 0; i < sockets_.size(); ++i) {
      filters[i] = (i == cereal::Event::Which::INIT_DATA || i == cereal::Event::Which::CAR_PARAMS || sockets_[i]);
    }
    // 设置图形渲染器的过滤器
    seg_mgr_->setFilters(filters);
  }
}

// 析构函数：清理资源并安全关闭所有线程
Replay::~Replay() {
  if (stream_thread_.joinable()) {
    rInfo("shutdown: in progress...");
    // 中断流线程并设置退出标志
    interruptStream([this]() {
      exit_ = true;
      return false;
    });
    // 等待流线程安全退出
    stream_thread_.join();
    rInfo("shutdown: done");
  }
  // 重置智能指针，释放相机服务器和段管理器资源
  camera_server_.reset();
  seg_mgr_.reset();
}

// 加载路由数据
bool Replay::load() {
  rInfo("loading route %s", seg_mgr_->route_.name().c_str());
  // 通过段管理器加载路由数据
  if (!seg_mgr_->load()) return false;

  // 计算路由的时间范围（以秒为单位）
  // 每个段代表60秒，所以段号乘以60得到秒数
  min_seconds_ = seg_mgr_->route_.segments().begin()->first * 60;        // 最小时间
  max_seconds_ = (seg_mgr_->route_.segments().rbegin()->first + 1) * 60; // 最大时间
  return true;
}

// 中断流线程执行
void Replay::interruptStream(const std::function<bool()> &update_fn) {
  // 如果流线程正在运行，发送信号中断其睡眠状态
  if (stream_thread_.joinable() && stream_thread_id) {
    pthread_kill(stream_thread_id, SIGUSR1);  // 发送SIGUSR1信号中断线程睡眠
  }
  {
    interrupt_requested_ = true;              // 设置中断请求标志
    std::unique_lock lock(stream_lock_);      // 获取流锁
    events_ready_ = update_fn();              // 执行更新函数并设置事件就绪状态
    interrupt_requested_ = user_paused_;      // 根据用户暂停状态更新中断标志
  }
  stream_cv_.notify_one();                    // 通知等待的流线程
}

// 跳转到指定时间点
void Replay::seekTo(double seconds, bool relative) {
  // 计算目标时间：相对时间或绝对时间
  double target_time = relative ? seconds + currentSeconds() : seconds;
  target_time = std::max(0.0, target_time);  // 确保时间不为负数
  
  // 计算目标段号（每60秒一个段）
  int target_segment = target_time / 60;
  
  // 检查目标段是否存在
  if (!seg_mgr_->hasSegment(target_segment)) {
    rWarning("Invalid seek to %.2f s (segment %d)", target_time, target_segment);
    return;
  }

  rInfo("Seeking to %d s, segment %d", (int)target_time, target_segment);
  notifyEvent(onSeeking, target_time);  // 通知开始跳转事件

  // 中断当前流并更新状态
  interruptStream([&]() {
    current_segment_.store(target_segment);                           // 设置当前段
    cur_mono_time_ = route_start_ts_ + target_time * 1e9;            // 更新当前时间戳（纳秒）
    cur_which_ = cereal::Event::Which::INIT_DATA;                    // 重置事件类型
    seeking_to_.store(target_time, std::memory_order_relaxed);       // 设置跳转目标时间
    return false;  // 暂停事件处理
  });

  seg_mgr_->setCurrentSegment(target_segment);  // 设置段管理器的当前段
  checkSeekProgress();                          // 检查跳转进度
}

// 检查跳转进度
void Replay::checkSeekProgress() {
  // 如果目标段还未加载完成，直接返回
  if (!seg_mgr_->getEventData()->isSegmentLoaded(current_segment_.load())) return;

  // 原子性地获取跳转目标时间并重置为-1
  double seek_to = seeking_to_.exchange(-1.0, std::memory_order_acquire);
  
  // 如果有有效的跳转目标且回调函数存在，则通知跳转完成
  if (seek_to >= 0 && onSeekedTo) {
    onSeekedTo(seek_to);
  }

  // 恢复被中断的流处理
  interruptStream([]() { return true; });
}

// 跳转到指定标志位置
void Replay::seekToFlag(FindFlag flag) {
  // 在时间轴中查找下一个匹配的标志
  if (auto next = timeline_.find(currentSeconds(), flag)) {
    seekTo(*next - 2, false);  // 跳转到找到位置的前2秒
  }
}

// 暂停或恢复回放
void Replay::pause(bool pause) {
  // 只有当暂停状态发生变化时才执行操作
  if (user_paused_ != pause) {
    interruptStream([=]() {
      rWarning("%s at %.2f s", pause ? "paused..." : "resuming", currentSeconds());
      user_paused_ = pause;  // 更新用户暂停状态
      return !pause;         // 返回是否应该继续处理事件
    });
  }
}

// 处理段合并事件
void Replay::handleSegmentMerge() {
  if (exit_) return;  // 如果正在退出，直接返回

  auto event_data = seg_mgr_->getEventData();
  
  // 如果流线程未运行且有可用段，启动流线程
  if (!stream_thread_.joinable() && !event_data->segments.empty()) {
    startStream(event_data->segments.begin()->second);
  }
  
  notifyEvent(onSegmentsMerged);  // 通知段合并完成事件

  // 中断流以处理段合并
  interruptStream([]() { return false; });
  checkSeekProgress();  // 检查跳转进度
}

// 启动数据流处理
void Replay::startStream(const std::shared_ptr<Segment> segment) {
  const auto &events = segment->log->events;
  
  // 设置路由开始时间戳（使用第一个事件的时间）
  route_start_ts_ = events.front().mono_time;
  cur_mono_time_ += route_start_ts_ - 1;

  // 获取路由日期时间：优先从INIT_DATA获取，否则使用路由名称中的时间
  route_date_time_ = route().datetime();
  
  // 查找INIT_DATA事件以获取准确的时间戳
  auto it = std::find_if(events.cbegin(), events.cend(),
                         [](const Event &e) { return e.which == cereal::Event::Which::INIT_DATA; });
  if (it != events.cend()) {
    capnp::FlatArrayMessageReader reader(it->data);
    auto event = reader.getRoot<cereal::Event>();
    uint64_t wall_time = event.getInitData().getWallTimeNanos();
    if (wall_time > 0) {
      route_date_time_ = wall_time / 1e6;  // 转换纳秒到毫秒
    }
  }

  // 写入车辆参数（CarParams）
  it = std::find_if(events.begin(), events.end(), 
                    [](const Event &e) { return e.which == cereal::Event::Which::CAR_PARAMS; });
  if (it != events.end()) {
    capnp::FlatArrayMessageReader reader(it->data);
    auto event = reader.getRoot<cereal::Event>();
    
    // 保存车辆指纹信息
    car_fingerprint_ = event.getCarParams().getCarFingerprint();

    // 将CarParams序列化并保存到参数存储
    capnp::MallocMessageBuilder builder;
    builder.setRoot(event.getCarParams());
    auto words = capnp::messageToFlatArray(builder);
    auto bytes = words.asBytes();
    
    // 保存到两个不同的参数键（临时和持久）
    Params().put("CarParams", (const char *)bytes.begin(), bytes.size());
    Params().put("CarParamsPersistent", (const char *)bytes.begin(), bytes.size());
  } else {
    rWarning("failed to read CarParams from current segment");
  }

  // 启动相机服务器（如果未禁用VisionIPC）
  if (!hasFlag(REPLAY_FLAG_NO_VIPC)) {
    std::pair<int, int> camera_size[MAX_CAMERAS] = {};  // 初始化相机尺寸数组
    
    // 遍历所有相机类型，获取每个相机的分辨率
    for (auto type : ALL_CAMERAS) {
      if (auto &fr = segment->frames[type]) {
        camera_size[type] = {fr->width, fr->height};
      }
    }
    
    // 创建相机服务器实例
    camera_server_ = std::make_unique<CameraServer>(camera_size);
  }

  // 初始化时间轴（用于快速查找和导航）
  timeline_.initialize(seg_mgr_->route_, route_start_ts_, 
                      !(flags_ & REPLAY_FLAG_NO_FILE_CACHE),  // 是否启用文件缓存
                      [this](std::shared_ptr<LogReader> log) { 
                        notifyEvent(onQLogLoaded, log);       // QLog加载完成回调
                      });

  // 启动流处理线程
  stream_thread_ = std::thread(&Replay::streamThread, this);
}

// 发布消息事件
void Replay::publishMessage(const Event *e) {
  // 如果设置了事件过滤器且事件被过滤，直接返回
  if (event_filter_ && event_filter_(e)) return;

  if (!sm_) {
    // 使用PubMaster发布消息
    auto bytes = e->data.asBytes();
    int ret = pm_->send(sockets_[e->which], (capnp::byte *)bytes.begin(), bytes.size());
    
    // 如果发送失败（通常是多发布者错误），停止发布该类型消息
    if (ret == -1) {
      rWarning("stop publishing %s due to multiple publishers error", sockets_[e->which]);
      sockets_[e->which] = nullptr;
    }
  } else {
    // 使用SubMaster模式更新消息
    capnp::FlatArrayMessageReader reader(e->data);
    auto event = reader.getRoot<cereal::Event>();
    sm_->update_msgs(nanos_since_boot(), {{sockets_[e->which], event}});
  }
}

// 发布视频帧
void Replay::publishFrame(const Event *e) {
  CameraType cam;
  
  // 根据事件类型确定相机类型
  switch (e->which) {
    case cereal::Event::ROAD_ENCODE_IDX: cam = RoadCam; break;      // 道路相机
    case cereal::Event::DRIVER_ENCODE_IDX: cam = DriverCam; break;  // 驾驶员相机
    case cereal::Event::WIDE_ROAD_ENCODE_IDX: cam = WideRoadCam; break; // 广角道路相机
    default: return;  // 无效的事件类型
  }

  // 检查相机是否被禁用
  if ((cam == DriverCam && !hasFlag(REPLAY_FLAG_DCAM)) || 
      (cam == WideRoadCam && !hasFlag(REPLAY_FLAG_ECAM)))
    return;  // 相机被禁用，不发布帧

  // 查找对应的段并发布帧数据
  auto seg_it = event_data_->segments.find(e->eidx_segnum);
  if (seg_it != event_data_->segments.end()) {
    if (auto &frame = seg_it->second->frames[cam]; frame) {
      camera_server_->pushFrame(cam, frame.get(), e);
    }
  }
}

// 流处理线程主函数
void Replay::streamThread() {
  stream_thread_id = pthread_self();  // 保存线程ID用于信号处理
  std::unique_lock lk(stream_lock_);  // 获取流锁

  while (true) {
    // 等待条件：退出或（事件就绪且未被中断）
    stream_cv_.wait(lk, [this]() { 
      return exit_ || (events_ready_ && !interrupt_requested_); 
    });
    
    if (exit_) break;  // 如果需要退出，结束循环

    // 获取事件数据
    event_data_ = seg_mgr_->getEventData();
    const auto &events = event_data_->events;
    
    // 查找大于当前时间戳的第一个事件
    auto first = std::upper_bound(events.cbegin(), events.cend(), 
                                 Event(cur_which_, cur_mono_time_, {}));
    
    // 如果没有更多事件，等待新事件
    if (first == events.cend()) {
      rInfo("waiting for events...");
      events_ready_ = false;
      continue;
    }

    // 发布事件并获取停止位置
    auto it = publishEvents(first, events.cend());

    // 确保在解锁前所有帧都已发送，防止竞态条件
    if (camera_server_) {
      camera_server_->waitForSent();
    }

    // 如果到达路由末尾且启用了循环模式，重新开始
    if (it == events.cend() && !hasFlag(REPLAY_FLAG_NO_LOOP)) {
      int last_segment = seg_mgr_->route_.segments().rbegin()->first;
      if (event_data_->isSegmentLoaded(last_segment)) {
        rInfo("reaches the end of route, restart from beginning");
        stream_lock_.unlock();
        seekTo(minSeconds(), false);  // 跳转到开始位置
        stream_lock_.lock();
      }
    }
  }
}

// 发布事件序列，返回停止位置的迭代器
std::vector<Event>::const_iterator Replay::publishEvents(std::vector<Event>::const_iterator first,
                                                         std::vector<Event>::const_iterator last) {
  uint64_t evt_start_ts = cur_mono_time_;    // 事件开始时间戳
  uint64_t loop_start_ts = nanos_since_boot(); // 循环开始时间戳
  double prev_replay_speed = speed_;         // 上一次的回放速度

  // 遍历事件序列
  for (; !interrupt_requested_ && first != last; ++first) {
    const Event &evt = *first;

    // 计算当前事件所属的段号
    int segment = toSeconds(evt.mono_time) / 60;
    
    // 如果段号发生变化，更新当前段
    if (current_segment_.load(std::memory_order_relaxed) != segment) {
      current_segment_.store(segment, std::memory_order_relaxed);
      seg_mgr_->setCurrentSegment(segment);
    }

    // 更新当前时间戳和事件类型
    cur_mono_time_ = evt.mono_time;
    cur_which_ = evt.which;

    // 如果没有对应的socket，跳过该事件
    if (!sockets_[evt.which]) continue;

    const uint64_t current_nanos = nanos_since_boot();
    // 计算时间差：考虑回放速度的事件时间与实际经过时间的差值
    const int64_t time_diff = (evt.mono_time - evt_start_ts) / speed_ - (current_nanos - loop_start_ts);

    // 重置时间戳以处理潜在的同步问题：
    // - 负的time_diff可能表示执行缓慢或系统唤醒
    // - 超过1秒的time_diff表示可能跳过了段
    if ((time_diff < -1e9 || time_diff >= 1e9) || speed_ != prev_replay_speed) {
      evt_start_ts = evt.mono_time;
      loop_start_ts = current_nanos;
      prev_replay_speed = speed_;
    } else if (time_diff > 0) {
      // 如果需要等待，进行精确的纳秒级睡眠
      precise_nano_sleep(time_diff, interrupt_requested_);
    }

    if (interrupt_requested_) break;  // 如果被中断，退出循环

    // 处理不同类型的事件
    if (evt.eidx_segnum == -1) {
      publishMessage(&evt);
    } else if (camera_server_) {
      if (speed_ > 1.0) {
        camera_server_->waitForSent();
      }
      publishFrame(&evt);
    }
  }

  return first;
}
