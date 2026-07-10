#!/usr/bin/env bash
# 连续 py-spy 采样脚本，固定参数不中途更改（第十节方法论）
# 用法: ./pyspy_sample.sh <pid> <sudo_password>
PID=$1
PASS=$2
for i in $(seq 1 10); do
  echo "=== sample $i at $(date +%T.%N) ==="
  echo "$PASS" | sudo -S /home/car/.local/bin/py-spy dump --pid "$PID" 2>&1 | grep -v '^\[sudo\]'
  sleep 3
done
