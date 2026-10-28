#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if ! command -v node >/dev/null 2>&1; then
  echo "请先安装 Node.js 22.12 或以上版本。"
  read -r "?按 Enter 退出…"
  exit 1
fi
node scripts/preview.mjs
