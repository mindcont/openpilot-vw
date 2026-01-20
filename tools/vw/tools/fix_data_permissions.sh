#!/usr/bin/env bash
# 修复 /data 目录权限脚本

echo "=== 修复 /data 目录权限 ==="

# 检查是否以root权限运行
if [ "$EUID" -eq 0 ]; then
    echo "检测到root权限，直接修复..."
    
    # 创建目录结构
    mkdir -p /data/{logs,media/0/realdata,params,stats}
    
    # 修改所有权
    chown -R $SUDO_USER:$SUDO_USER /data
    
    # 设置权限
    chmod -R 755 /data
    
    echo "✓ /data 目录权限修复完成"
    echo "所有者: $SUDO_USER:$SUDO_USER"
    echo "权限: 755"
    
else
    echo "需要sudo权限来修复 /data 目录权限"
    echo "正在请求sudo权限..."
    
    # 使用sudo重新运行此脚本
    sudo "$0" "$@"
fi

echo
echo "验证权限设置:"
ls -la /data/
echo
echo "测试写入权限:"
if touch /data/test_write 2>/dev/null; then
    echo "✓ /data 目录可写"
    rm -f /data/test_write
else
    echo "✗ /data 目录不可写"
    exit 1
fi

echo
echo "权限修复完成！现在可以启动 openpilot 了。"