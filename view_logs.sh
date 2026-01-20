#!/usr/bin/env bash
# openpilot 日志查看工具

show_help() {
    echo "openpilot 日志查看工具"
    echo
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  -c, --console     查看最新的控制台日志"
    echo "  -s, --swaglog     查看最新的系统日志"
    echo "  -d, --data        查看数据记录目录"
    echo "  -a, --all         查看所有日志类型"
    echo "  -f, --follow      实时跟踪日志"
    echo "  -h, --help        显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0 -c             # 查看控制台日志"
    echo "  $0 -s -f          # 实时跟踪系统日志"
    echo "  $0 -a             # 查看所有日志"
}

view_console_log() {
    local follow_flag=""
    if [ "$1" = "-f" ]; then
        follow_flag="-f"
    fi
    
    echo "=== 控制台日志 ==="
    local latest_console=$(ls -t /data/logs/console_*.log 2>/dev/null | head -1)
    if [ -n "$latest_console" ]; then
        echo "文件: $latest_console"
        echo "大小: $(du -h "$latest_console" | cut -f1)"
        echo
        tail $follow_flag -n 50 "$latest_console"
    else
        echo "未找到控制台日志文件"
    fi
}

view_swaglog() {
    local follow_flag=""
    if [ "$1" = "-f" ]; then
        follow_flag="-f"
    fi
    
    echo "=== 系统日志 (swaglog) ==="
    local latest_swaglog=$(ls -t /data/logs/swaglog.* 2>/dev/null | head -1)
    if [ -n "$latest_swaglog" ]; then
        echo "文件: $latest_swaglog"
        echo "大小: $(du -h "$latest_swaglog" | cut -f1)"
        echo
        tail $follow_flag -n 50 "$latest_swaglog"
    else
        echo "未找到系统日志文件"
    fi
}

view_data_logs() {
    echo "=== 数据记录目录 ==="
    if [ -d "/data/media/0/realdata" ]; then
        echo "最新的5个数据段:"
        ls -lt /data/media/0/realdata/ | head -6
        echo
        echo "总数据大小: $(du -sh /data/media/0/realdata 2>/dev/null | cut -f1)"
    else
        echo "未找到数据记录目录"
    fi
}

view_all_logs() {
    echo "=== openpilot 日志概览 ==="
    echo
    
    # 磁盘使用情况
    echo "磁盘使用情况:"
    df -h /data 2>/dev/null || df -h /
    echo
    
    # 各类日志统计
    echo "日志文件统计:"
    echo "控制台日志: $(ls /data/logs/console_*.log 2>/dev/null | wc -l) 个文件"
    echo "系统日志: $(ls /data/logs/swaglog.* 2>/dev/null | wc -l) 个文件"
    echo "数据段: $(ls -d /data/media/0/realdata/*/ 2>/dev/null | wc -l) 个目录"
    echo
    
    # 最新日志
    view_console_log
    echo
    view_swaglog
    echo
    view_data_logs
}

# 主程序
case "$1" in
    -c|--console)
        view_console_log "$2"
        ;;
    -s|--swaglog)
        view_swaglog "$2"
        ;;
    -d|--data)
        view_data_logs
        ;;
    -a|--all)
        view_all_logs
        ;;
    -f|--follow)
        if [ "$2" = "-c" ] || [ "$2" = "--console" ]; then
            view_console_log "-f"
        elif [ "$2" = "-s" ] || [ "$2" = "--swaglog" ]; then
            view_swaglog "-f"
        else
            echo "错误: -f 必须与 -c 或 -s 一起使用"
            show_help
            exit 1
        fi
        ;;
    -h|--help|"")
        show_help
        ;;
    *)
        echo "错误: 未知选项 '$1'"
        show_help
        exit 1
        ;;
esac