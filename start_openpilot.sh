#!/usr/bin/env bash
# openpilot 一键启动脚本
# 自动处理目录切换、虚拟环境激活和权限设置

# 脚本配置
OPENPILOT_DIR="/home/wio/openpilot"
VENV_PATH="$OPENPILOT_DIR/.venv"
DATA_DIR="/data"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查并创建目录
setup_directories() {
    log_info "设置数据目录..."
    
    # 检查/data目录权限
    if [ -d "$DATA_DIR" ]; then
        if [ ! -w "$DATA_DIR" ]; then
            log_warning "/data目录权限不足，尝试修复..."
            sudo chown -R $USER:$USER $DATA_DIR 2>/dev/null || {
                log_error "无法修改/data权限，请手动执行: sudo chown -R $USER:$USER /data"
                log_info "或者运行: sudo chmod 777 /data"
                exit 1
            }
        fi
        log_success "/data目录权限正常"
    else
        log_warning "/data目录不存在，创建中..."
        sudo mkdir -p $DATA_DIR/{logs,media/0/realdata,params,stats} 2>/dev/null || {
            log_error "无法创建/data目录，请手动执行: sudo mkdir -p /data"
            exit 1
        }
        sudo chown -R $USER:$USER $DATA_DIR 2>/dev/null
    fi
    
    # 确保必要目录存在且有正确权限
    mkdir -p $DATA_DIR/{logs,media/0/realdata,params,stats} 2>/dev/null
    chmod 755 $DATA_DIR/{logs,media/0/realdata,params,stats} 2>/dev/null
    
    # 备用目录（以防万一）
    mkdir -p ~/.comma/{log,media/0/realdata,params,stats} 2>/dev/null
    mkdir -p /tmp/data/logs 2>/dev/null
    
    return 0
}

# 检查openpilot目录
check_openpilot_dir() {
    if [ ! -d "$OPENPILOT_DIR" ]; then
        log_error "openpilot目录不存在: $OPENPILOT_DIR"
        exit 1
    fi
    
    if [ ! -f "$OPENPILOT_DIR/launch_openpilot.sh" ]; then
        log_error "launch_openpilot.sh不存在"
        exit 1
    fi
    
    log_success "openpilot目录检查通过"
}

# 检查并激活虚拟环境
setup_venv() {
    if [ -d "$VENV_PATH" ]; then
        log_info "激活虚拟环境..."
        source "$VENV_PATH/bin/activate"
        log_success "虚拟环境已激活: $(which python3)"
    else
        log_warning "虚拟环境不存在: $VENV_PATH"
        log_info "使用系统Python: $(which python3)"
    fi
}

# 设置环境变量
setup_environment() {
    log_info "设置环境变量..."
    
    # 基础环境变量
    export PC=1
    export PASSIVE=1
    export OPENPILOT_DATA=/tmp/data
    export LOGPRINT=info
    
    # 强制使用/data目录存储日志
    export LOG_ROOT="$DATA_DIR/media/0/realdata"
    log_success "强制使用/data目录存储日志: $LOG_ROOT"
    
    # 其他配置
    export SKIP_FW_QUERY=1
    export NOBOARD=1
    export BIG=1
    
    # 线程数限制
    export OMP_NUM_THREADS=1
    export MKL_NUM_THREADS=1
    export NUMEXPR_NUM_THREADS=1
    export OPENBLAS_NUM_THREADS=1
    export VECLIB_MAXIMUM_THREADS=1
    
    log_success "环境变量设置完成"
}

# 显示启动信息
show_startup_info() {
    echo
    log_info "=== openpilot 启动信息 ==="
    echo "工作目录: $OPENPILOT_DIR"
    echo "虚拟环境: ${VIRTUAL_ENV:-系统Python}"
    echo "数据目录: $LOG_ROOT"
    echo "swaglog目录: /data/logs"
    echo "参数目录: /data/params"
    echo "统计目录: /data/stats"
    echo "日志级别: $LOGPRINT"
    echo "PC模式: $PC"
    echo "被动模式: $PASSIVE"
    
    # 检查目录权限
    echo
    log_info "=== 目录权限检查 ==="
    for dir in "/data/logs" "/data/media/0/realdata" "/data/params" "/data/stats"; do
        if [ -w "$dir" ]; then
            echo "✓ $dir (可写)"
        else
            echo "✗ $dir (不可写)"
        fi
    done
    echo
}

# 启动openpilot
start_openpilot() {
    log_info "启动openpilot..."
    
    cd "$OPENPILOT_DIR" || {
        log_error "无法切换到openpilot目录"
        exit 1
    }
    
    # 检查是否有其他实例在运行
    if pgrep -f "manager.py" > /dev/null; then
        log_warning "检测到openpilot已在运行"
        read -p "是否要停止现有实例并重新启动? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "停止现有实例..."
            pkill -f "manager.py" 2>/dev/null
            sleep 2
        else
            log_info "取消启动"
            exit 0
        fi
    fi
    
    # 启动openpilot
    log_success "正在启动openpilot..."
    exec ./launch_openpilot.sh
}

# 主函数
main() {
    echo -e "${BLUE}"
    echo "=================================="
    echo "    openpilot 一键启动脚本"
    echo "=================================="
    echo -e "${NC}"
    
    # 执行启动步骤
    check_openpilot_dir
    setup_directories
    setup_venv
    setup_environment
    show_startup_info
    
    # 询问是否继续
    read -p "按Enter键继续启动，或Ctrl+C取消..." -r
    
    start_openpilot
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi