import os
import requests
from urllib.parse import urlparse
from openpilot.tools.lib.route import Route

# 下载目录
download_dir = "/data"
os.makedirs(download_dir, exist_ok=True)

# 获取路由信息
route = Route("a2a0ccea32023010|2023-07-27--13-01-19")

# 下载所有文件
for segment in route.segments:
    if segment.log_path:
        url = segment.log_path
        filename = os.path.basename(urlparse(url).path)
        filepath = os.path.join(download_dir, f"{segment.name.canonical_name}_{filename}")
        
        if os.path.exists(filepath):
            print(f"跳过已存在: {filepath}")
            continue
            
        print(f"下载: {url} -> {filepath}")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"完成: {filepath}")
        except Exception as e:
            print(f"失败: {e}")
