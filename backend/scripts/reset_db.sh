#!/usr/bin/env bash
# 删除 dev.db 并重跑迁移。**仅开发环境使用**。
set -e

cd "$(dirname "$0")/.."

if [[ -f dev.db ]]; then
  echo "→ 删除 dev.db"
  rm -f dev.db
fi

echo "→ alembic upgrade head"
alembic upgrade head

echo "✓ 数据库已重置。下次启动 uvicorn 将自动 sync RBAC + 种子。"
