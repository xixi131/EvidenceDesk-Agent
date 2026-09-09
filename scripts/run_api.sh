#!/usr/bin/env bash
# 一键起 API 服务：先切到项目根目录，绕开本机代理对中转站域名的握手问题，
# 再用项目虚拟环境里的 uvicorn 启动，--reload 方便改代码自动重启。
set -euo pipefail
cd "$(dirname "$0")/.."

export NO_PROXY="www.898880.xyz${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

# 模型文件已经在本地缓存过了（.cache/huggingface），不需要每次启动都联网去
# Hugging Face 确认「有没有更新」——这个检查请求经常超时重试，是启动慢/卡住
# 的真正原因。设成 offline 模式后，huggingface_hub 库直接用本地缓存，跳过
# 所有联网校验。
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

.venv/bin/uvicorn evidence_desk.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
