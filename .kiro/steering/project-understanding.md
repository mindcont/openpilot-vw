---
inclusion: always
---

# openpilot-vw 项目理解

> 本文件是项目全局理解快照，随重要进展更新。详细文档见 `learn-docs/`（有 README 索引）。

## 项目定位

**openpilot-vw** 是 [commaai/openpilot](https://github.com/commaai/openpilot) 的个人 fork，
目标车辆 **24 款大众速腾（MQB 平台，中配）**。当前目标：**纯视觉车道显示 + 轨迹预测，
不控车**。控车（横向/纵向）是远期延伸，非当前目标。

## 仓库

| 项 | 详情 |
|----|------|
| origin | `git@github.com:mindcont/openpilot-vw.git` |
| upstream | `https://github.com/commaai/openpilot.git` |
| 活跃分支 | `dev-vw`（默认） |
| 子模块 | panda、opendbc_repo、msgq_repo、rednose_repo、teleoprtc_repo、tinygrad_repo |

## 两种运行方式

1. **PC 纯视觉验证（已跑通）**：`python3 run_laneline_demo.py`
   - 用 `tools/webcam/demo2.mp4` 当摄像头输入，主进程内跑 `AugmentedRoadView` 渲染车道线
   - `NO_UI=1` 走纯终端，打印 `modelV2` 的 `laneLineProbs`/车道线坐标
2. **Orin NX 生产部署（脚本就绪，未实机验证）**：`./start_openpilot_orinnx.sh`
   - 走正规 manager 流程，双摄像头（road + wide），真实 CAN

关键环境变量：`USE_WEBCAM=1`、`FINGERPRINT=VOLKSWAGEN_GOLF_MK7`（代理指纹）、
`PASSIVE=1`、`NOBOARD=1`、`FORCE_ONROAD=1`、`BIG=1`（大屏 UI）。
⚠️ **切勿设 `IsDriverViewEnabled=True`**——会触发 `not_driver_view=False` 阻塞 onroad 启动。

## 本会话关键实证结论

### 纯视觉车道线预测已跑通
demo.mp4 → webcamerad → VisionIPC → modeld → modelV2 → UI 叠加，`laneLineProbs` 达 0.9+。
车道预测只需车速，不需要 CAN 也能出车道线。

### 目标平台是 Jetson Orin NX（非 TX2）
无 `/TICI` → openpilot 视角 `PC=True`，所有 `if PC:` 适配自动生效。算力足够跑满 20fps。

### CAN 抓包解析（J533 静止点火，vw_mqb.dbc）
- **DBC 用 `vw_mqb.dbc`**（匹配度最高 68%），不是 vw_mqb_20.dbc
- bus0=动力总成，bus2=bus0 镜像，bus1 更全；openpilot 读 `Bus.pt`=bus0
- 车道预测/carState 所需信号**全部可获取**：车速 `ESP_19` 四轮速、方向盘
  `LWI_01.LWI_Lenkradwinkel`、档位 `Gateway_73.GE_Fahrstufe`（自动挡=DSG）等 17 个 carstate 依赖消息全在 bus0
- **ACC 前车雷达：硬件在位但未编码**（`ACC_06.ACC_Typ=ACC_nicht_codiert`），
  所有距离/目标信号为空值 → 当前拿不到前车距离（车道预测不需要）
- **横向控制硬件实测具备**：`HCA_01(0x126)` 在总线广播（原厂 R242 车道保持相机）、
  `EPS_HCA_Status=initializing`（非 DISABLED，EPS 支持转向注入）、`LDW_02` 在

### 分阶段路线
- **第一阶段（当前）**：纯视觉车道预测，PC 已跑通，Orin NX 待实机
- **第二阶段**：接入真实 CAN（读车速/方向盘）→ 已评估可完全满足不控车+预测，
  额外带来真实车速、在线标定、完整车辆状态
- **完整 openpilot（远期）**：横向硬件已具备、需开通 ACC（纵向）；
  **真正门槛是可写 panda + 相机中间人 harness**（当前旁路只读）+ 去 PASSIVE/NOBOARD

## 关键技术修复点（避免重复踩坑）

1. **tinygrad 版本必须匹配模型 pkl**：子模块激进更新会导致 `modeld` 反序列化崩溃
   （`Ops.SLICE` 断言）。已锁定 `tinygrad_repo` 到与 `.pkl` 兼容的 commit（d60a155e4）。
   子模块整体已回退到 #027 对应版本。
2. **PC 模式默认标定**：`modeld.py` 在 PC 下直接设默认标定矩阵（`live_calib_seen=True`），
   否则 transform 为零、车道线置信度≈0。
3. **摄像头 intrinsics 必须匹配分辨率**：错误会导致投影错位、prob≈0。视频缩放到
   1928×1208 匹配 comma AR/OX 参数；生产用 `ROAD_CAM_INTRINSICS`/`WIDE_CAM_INTRINSICS` 注入实测标定值。
4. **UI 用大屏布局**：`BIG=1` 走 `MainLayout`（含车道线叠加），否则用 mici 小屏布局。
5. **FORCE_ONROAD**：无 panda 平台靠它进 onroad 拉起 modeld/UI（改在 `hardwared.py`）。

## 关键文件

| 文件 | 作用 |
|------|------|
| `run_laneline_demo.py` | PC 纯视觉车道线验证（主进程内渲染，绕过 manager 时序问题） |
| `start_openpilot_orinnx.sh` | Orin NX 双摄像头生产启动（正规 manager 流程） |
| `start_openpilot.sh` | PC 通用一键启动 |
| `tools/webcam/camerad.py` `camera.py` | webcam 采集，支持视频文件/双摄独立分辨率 |
| `tools/vw/can_analysis/` | CAN 抓包解析工具（5 个脚本，见下） |
| `system/hardware/hardwared.py` | 含 FORCE_ONROAD 改动 |
| `selfdrive/ui/onroad/` | AugmentedRoadView/ModelRenderer（车道线蓝色叠加）+ PC 适配 |
| `learn-docs/README.md` | 全部学习文档的分类索引（✅有效/📖参考/🗄️归档） |

## CAN 分析工具（tools/vw/can_analysis/，依赖 cantools）

| 脚本 | 作用 |
|------|------|
| `analyze_match.py` | DBC 匹配度分析（选 DBC） |
| `decode_can.py` | 关键车辆信号解析 |
| `full_scan.py` | 全量三总线扫描 + 关键信号评估 |
| `acc_radar.py` | ACC 前车雷达距离专项评估 |
| `check_carstate_deps.py` | carState 依赖消息核对 |
| `check_lateral_deps.py` | 横向控制前提核查（HCA/EPS/网络位置） |

用法均为 `python3 <脚本> <csv> <dbc>`；抓包数据在 `~/cabana_live_stream/`。

## 技术栈

构建 SCons；包管理 uv；序列化 Cap'n Proto（cereal）；IPC msgq/ZMQ；
AI 推理 tinygrad；视频 VisionIPC/YUV；目标平台 PC(Ubuntu 24.04)/Jetson Orin NX(JetPack 7.2=24.04)。

## 开发注意事项

1. **子模块**：`git submodule update --init` 恢复到主 repo 记录版本；勿随意
   `--remote` 更新 tinygrad（会与模型 pkl 不兼容）。
2. **文档整理约定**：过时文档移入 `learn-docs/车型适配/archive/`（git mv 保留历史），
   `learn-docs/README.md` 维护分类索引与时效状态。
3. **`opendbc_repo` 下 `*_generated.dbc`** 是构建产物，会被 `git clean -fd` 清理。
4. **虚拟环境** `.venv/` 已配置。
5. **提交规范**：改动完成后按功能聚焦提交；文档/工具改动与代码改动分开提交。
