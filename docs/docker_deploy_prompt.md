# Docker 化部署:本地 + ECS 一键自动部署

## 背景

当前演示部署链路依赖 rsync + ECS 上手动 build,每次演示要手动操作十几步,且前端跑在 dev 模式、Dockerfile 是临时拼凑的瘦身版,不具备长期使用价值。

本次目标:把项目改造成可重复、可自动化的容器化部署,**main 分支 push 后自动部署到 ECS**,数据不丢、迁移不漏、回滚可控。

**核心原则**:Docker 只用于「部署 + 演示」,本地开发仍走 `uvicorn --reload` + `pnpm dev`,不要逼自己每次改代码都 rebuild 镜像。

**本次改动范围严格限定**:Dockerfile / compose / 部署脚本 / CI / seed 幂等化 / CLAUDE.md 约束同步。**不动**业务代码、不动 RBAC、不动审计、不动数据库 schema。

---

## 不在本次范围(明确排除)

- ❌ HTTPS / 域名 / 证书(MVP 阶段公网 IP 直连即可)
- ❌ Nginx / 反向代理(Next.js 自身 listen 即可)
- ❌ Redis / 队列 / 缓存层
- ❌ Kubernetes / Swarm / 镜像仓库(单机 compose 足够,build 在 ECS 本地)
- ❌ 多环境(staging / prod)分离(MVP 只有一个演示环境)
- ❌ 蓝绿 / 金丝雀部署(直接重启即可)
- ❌ 集中式日志收集(docker logs 够用)
- ❌ 监控告警接入

---

## 技术决策(已确认)

| 决策点 | 选择 | 理由 |
|---|---|---|
| 镜像构建位置 | ECS 本地 build,不推 registry | 单机部署,简化链路 |
| 数据库容器化 | ✅ 是 | 演示环境零依赖,clone+up 即可 |
| 数据持久化 | named volume `overseas_platform_pgdata` | 容器重建不丢数据 |
| 部署触发 | `push origin main` 触发 GitHub Actions | 独立开发,main 即 demo 版本 |
| 前端运行模式 | `next build` + `next start`(生产) | 不再用 dev 模式 |
| 前端包管理 | **pnpm**(改回,不要用 npm) | 与 CLAUDE.md 锁定栈一致 |
| 后端包管理 | **uv** | 同上 |
| 迁移策略 | 容器 entrypoint 内自动 `alembic upgrade head` | 启动即就绪 |
| Seed 策略 | 全函数幂等(先查后写),启动时跑 | 安全可重入 |
| 回滚机制 | 部署前 `pg_dump` + 保留 7 天 + git reset 上一版重 build | 简单可靠 |
| 镜像 tag | **精确到 minor**(如 `postgres:16.4-alpine`) | 避免重 build 时被动升级 |
| 日志 | json-file driver,每服务 10m × 3 文件滚动 | 防磁盘塞满 |
| 老演示数据 | **迁移过去**(`pg_dump` 老库 → 新库 restore) | 领导可能正在用 |

---

## 一、文件清单

新增 / 修改如下文件:

```
.
├── backend/
│   ├── Dockerfile                       # 重写(生产级多阶段)
│   ├── .dockerignore                    # 检查 / 完善
│   ├── docker-entrypoint.sh             # 新增(自动迁移 + seed + 启动)
│   └── app/seed.py                      # 改造为幂等
│
├── frontend/
│   ├── Dockerfile                       # 重写(pnpm + standalone)
│   ├── .dockerignore                    # 检查 / 完善
│   └── next.config.mjs                  # 加 output: 'standalone'
│
├── docker-compose.yml                   # 重写(生产配置)
├── docker-compose.override.yml          # 删除(原演示用)
│
├── deploy/
│   ├── deploy.sh                        # ECS 上的部署脚本(被 CI 调用)
│   ├── check-migration-safety.sh        # 危险迁移拦截脚本
│   └── README.md                        # 部署说明 + 首次配置 checklist
│
├── .github/workflows/
│   └── deploy.yml                       # GitHub Actions 自动部署
│
├── .env.production.example              # 生产 env 模板(实际值不入 Git)
│
└── CLAUDE.md                            # 同步更新 Docker 相关约束
```

清理(放到一个独立 commit):
- 删除 `package-for-delivery.sh` / `start.command` / `stop.command`(演示交付脚本,不再使用)
- 删除当前演示用的 `docker-compose.override.yml`

---

## 二、后端 Dockerfile

文件:`backend/Dockerfile`

要求:
- **多阶段构建**:builder 阶段装依赖,runtime 阶段只拷必要产物
- **基础镜像**:`python:3.11.10-slim`(精确 minor;不要 alpine,asyncpg / bcrypt 编译麻烦)
- **包管理用 uv**(全程不要用 pip 直装,与 CLAUDE.md 一致)
- **apt 源换成阿里云**(否则 ECS 上慢到不可用,昨天踩过 48 分钟的坑)
- **uv 二进制不走 ghcr**(国内拉极慢),改用阿里云镜像或预下载方案
- **非 root 用户运行**(`appuser`)
- **暴露端口 8000**
- **加 HEALTHCHECK**(curl /healthz)
- **entrypoint 用 docker-entrypoint.sh**

参考结构:

```dockerfile
# ===== builder =====
FROM python:3.11.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 替换 apt 源为阿里云(关键!否则 apt-get install 极慢)
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv(从阿里云镜像或 pip 装,不走 ghcr)
RUN curl -fsSL https://mirrors.aliyun.com/pypi/simple/uv/ -o /dev/null \
    && pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# 装依赖到固定 venv 路径,runtime 阶段直接拷
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -e .

# ===== runtime =====
FROM python:3.11.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# 运行时依赖(libpq 给 psycopg) - apt 源同样换阿里云
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser . .

# entrypoint 需可执行
RUN chmod +x docker-entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/.dockerignore` 必须包含:`.venv`、`__pycache__`、`*.pyc`、`.pytest_cache`、`.env`、`tests/`、`scripts/`

**昨天踩过的坑(必须规避)**:
- ❌ Dockerfile 用 `deb.debian.org` 默认源 → apt 装 build-essential 跑了 48 分钟还没完
- ❌ `COPY --from=ghcr.io/astral-sh/uv:latest` → 国内拉镜像极慢
- ❌ pip 不指定 `--index-url` → 拉 PyPI 慢
- ❌ Docker daemon 配了 HTTP 代理但代理不通 → 整个 build 直接挂掉

---

## 三、后端 entrypoint

文件:`backend/docker-entrypoint.sh`(可执行,chmod 755)

职责:**等 DB 就绪 → 跑迁移 → 跑 seed → exec CMD**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] 等待数据库就绪..."
python -c "
import os, time, asyncio
import asyncpg
from urllib.parse import urlparse

url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg', 'postgresql')
parsed = urlparse(url)

async def wait():
    for i in range(60):
        try:
            conn = await asyncpg.connect(
                host=parsed.hostname, port=parsed.port,
                user=parsed.username, password=parsed.password,
                database=parsed.path.lstrip('/')
            )
            await conn.close()
            print(f'[entrypoint] 数据库就绪(第 {i+1} 次尝试)')
            return
        except Exception as e:
            print(f'[entrypoint] 等待 DB ({i+1}/60): {e}')
            await asyncio.sleep(2)
    raise SystemExit('数据库连接超时')

asyncio.run(wait())
"

echo '[entrypoint] 跑 alembic upgrade head'
alembic upgrade head

echo '[entrypoint] 跑 seed(幂等)'
python -m app.seed

echo '[entrypoint] 启动应用'
exec "$@"
```

**绝对禁止**:
- ❌ 在 entrypoint 里跑 `alembic downgrade`
- ❌ 在 entrypoint 里跑 `drop` / `truncate` / `delete`
- ❌ 在 entrypoint 里删除 / 清空任何数据

---

## 四、Seed 幂等化改造

文件:`backend/app/seed.py`

**当前问题**:seed 可能在每次容器启动时被调用,如果不是幂等的会重复插入或报唯一键冲突。

要求:**每个 seed 函数开头先查后写**。

模板:

```python
async def seed_super_admin(session: AsyncSession) -> None:
    existing = await session.scalar(
        select(User).where(User.email == settings.SUPER_ADMIN_EMAIL)
    )
    if existing:
        logger.info("[seed] super admin 已存在,跳过")
        return
    # 否则创建
    ...

async def seed_buyer_organization(session: AsyncSession) -> None:
    existing = await session.scalar(
        select(BuyerOrganization).where(BuyerOrganization.name == "中建三局")
    )
    if existing:
        logger.info("[seed] 中建三局组织已存在,跳过")
        return
    ...

# 其他 seed 函数同样处理
```

**RBAC 启动同步**(权限点 / 角色绑定):如已实现幂等,确认即可。如未实现,在权限插入前先 `select` 一遍,存在的更新 description,不存在的插入。**严禁** `delete + insert` 模式。

---

## 五、前端 Dockerfile

文件:`frontend/Dockerfile`

要求:
- **多阶段构建**:deps → builder → runner
- **pnpm**(全程不要 npm,与 CLAUDE.md 锁定栈一致)
- **基础镜像精确**:`node:20.18-alpine`
- **pnpm 版本锁定**:从 `package.json` 的 `packageManager` 字段或固定版本号,**不要用 `pnpm@latest`**(昨天踩过 ERR_UNKNOWN_BUILTIN_MODULE)
- **npm registry 换淘宝镜像**:加速 pnpm install
- **Next.js standalone 输出**(`next.config.mjs` 加 `output: 'standalone'`)
- **非 root 用户运行**(`nextjs:nodejs`)
- **暴露端口 3000**
- **生产模式启动**,不要 dev / hot reload

```dockerfile
# ===== deps =====
FROM node:20.18-alpine AS deps
# 国内 npm 镜像加速 + pnpm 版本锁定
RUN npm config set registry https://registry.npmmirror.com \
    && corepack enable \
    && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm config set registry https://registry.npmmirror.com \
    && pnpm install --frozen-lockfile

# ===== builder =====
FROM node:20.18-alpine AS builder
RUN npm config set registry https://registry.npmmirror.com \
    && corepack enable \
    && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 注意:NEXT_PUBLIC_* 必须在 build 时注入,client 包打进 bundle
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN pnpm build

# ===== runner =====
FROM node:20.18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs \
    && apk add --no-cache wget

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000 > /dev/null || exit 1

CMD ["node", "server.js"]
```

**pnpm 版本说明**:
- 执行实施步骤 0 时,跑 `pnpm --version` 看本地版本,把上面 `pnpm@9.12.0` 替换成你本地实际版本
- 同时在 `frontend/package.json` 顶层加 `"packageManager": "pnpm@9.12.0"`(corepack 会自动识别)
- **不要**用 `pnpm@latest`,跨版本可能有破坏性变更

**昨天踩过的坑(必须规避)**:
- ❌ `corepack prepare pnpm@latest` → 拉到的版本与本地不一致 → `ERR_UNKNOWN_BUILTIN_MODULE`
- ❌ 退路改 npm → 跟 CLAUDE.md 锁定栈不一致,后续维护两套 lockfile
- ❌ 不换 npm registry → pnpm install 拉国外源极慢

修改 `frontend/next.config.mjs`,加 `output: 'standalone'`:

```js
const nextConfig = {
  output: 'standalone',
  // ... 其他原有配置
}
```

`frontend/.dockerignore` 必须包含:`node_modules`、`.next`、`.env*.local`、`README.md`

**注意 NEXT_PUBLIC_API_BASE_URL 注入时机**:
- 这是 client-side 变量,**必须在 build 时**注入(`ARG` + `ENV`),不能 runtime 改
- 由 compose `build.args` 传入
- 值应为 ECS 公网 URL,如 `http://<ECS-IP>:8000`(不要写 localhost)

---

## 六、docker-compose.yml(生产版)

文件:`docker-compose.yml`

```yaml
x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:
  db:
    image: postgres:16.4-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
    # 不对外暴露 5432,只在 compose 内网可见
    expose:
      - "5432"
    logging: *default-logging

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      JWT_ALGORITHM: ${JWT_ALGORITHM:-HS256}
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES:-15}
      REFRESH_TOKEN_EXPIRE_DAYS: ${REFRESH_TOKEN_EXPIRE_DAYS:-7}
      SUPER_ADMIN_EMAIL: ${SUPER_ADMIN_EMAIL}
      SUPER_ADMIN_INITIAL_PASSWORD: ${SUPER_ADMIN_INITIAL_PASSWORD}
      CORS_ORIGINS: ${CORS_ORIGINS}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    logging: *default-logging

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "3000:3000"
    logging: *default-logging

volumes:
  pgdata:
    name: overseas_platform_pgdata
```

**关键约束**:
- ✅ `pgdata` 用 named volume,**有显式 `name:` 字段**(避免 compose project name 变化导致卷不一致)
- ✅ `restart: unless-stopped`(ECS 重启自动拉起)
- ✅ DB 不暴露公网端口
- ✅ 所有 secret 走环境变量,**不要写死在 yml 里**
- ✅ 所有服务都挂 `logging: *default-logging`,防磁盘塞满
- ✅ 镜像 tag 精确到 minor(`16.4-alpine` 不是 `16-alpine`)

---

## 七、`.env.production.example` 模板

文件:`.env.production.example`(入 Git,作为模板)

```bash
# 数据库
POSTGRES_DB=overseas_supply
POSTGRES_USER=overseas_app
POSTGRES_PASSWORD=<生产强密码,openssl rand -base64 24 生成>

# JWT
JWT_SECRET_KEY=<openssl rand -hex 32 生成>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# 初始超级管理员
SUPER_ADMIN_EMAIL=superadmin@platform.local
SUPER_ADMIN_INITIAL_PASSWORD=<首次部署后立即改密>

# CORS(允许前端域 / 公网 IP 访问后端)
CORS_ORIGINS=http://<ECS-公网-IP>:3000

# 前端访问后端的地址(build 时注入)
NEXT_PUBLIC_API_BASE_URL=http://<ECS-公网-IP>:8000

# 日志
LOG_LEVEL=INFO
```

实际值 `.env.production` **不入 Git**:
- 加入 `.gitignore`:`.env.production`、`.env`、`.env.local`
- 只在 ECS `/opt/overseas-platform/.env.production` 存在,文件权限 `chmod 600`

---

## 八、ECS 部署脚本

文件:`deploy/deploy.sh`(可执行)

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/overseas-platform}"
BACKUP_DIR="${APP_DIR}/backups"
RETENTION_DAYS=7

cd "$APP_DIR"

echo "[deploy] === 开始部署 $(date -Iseconds) ==="

# 1. 备份数据库(只在 DB 容器已存在且运行时备份)
mkdir -p "$BACKUP_DIR"
if docker compose ps db --format json 2>/dev/null | grep -q '"State":"running"'; then
    BACKUP_FILE="$BACKUP_DIR/$(date +%Y%m%d-%H%M%S).sql.gz"
    echo "[deploy] 备份数据库到 $BACKUP_FILE"
    docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
    # 清理 7 天前的备份
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
else
    echo "[deploy] DB 容器未运行,跳过备份(首次部署)"
fi

# 2. 拉最新代码
echo "[deploy] 拉取最新代码"
git fetch origin
git reset --hard origin/main

# 3. 加载 env(给 backup 步骤的 POSTGRES_USER 等用)
set -a
source .env.production
set +a

# 4. 重建容器(注意:严禁 -v!)
echo "[deploy] 重建并启动容器"
docker compose --env-file .env.production up -d --build --remove-orphans

# 5. 等服务起来(backend healthcheck 通过即认为 OK)
echo "[deploy] 等待 backend 健康..."
for i in $(seq 1 30); do
    if curl -fsS http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "[deploy] backend 健康(第 $i 次尝试)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[deploy] backend 健康检查超时,部署失败"
        exit 1
    fi
    sleep 2
done

# 6. 前端探活
echo "[deploy] 等待 frontend 健康..."
for i in $(seq 1 30); do
    if curl -fsS http://localhost:3000 > /dev/null 2>&1; then
        echo "[deploy] frontend 健康(第 $i 次尝试)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[deploy] frontend 健康检查超时,部署失败"
        exit 1
    fi
    sleep 2
done

# 7. 清理 dangling 镜像(可选,节省磁盘)
docker image prune -f --filter "dangling=true"

echo "[deploy] === 部署成功 $(date -Iseconds) ==="
```

**强约束**:
- ❌ 脚本里**不允许出现** `docker compose down -v`、`docker volume rm`、`docker system prune --volumes`
- ❌ 不允许 `git clean -fdx`(会删 backups/)
- ❌ 不允许 `rm -rf pgdata` 之类操作

---

## 九、迁移安全检查脚本

文件:`deploy/check-migration-safety.sh`

**用途**:CI 里跑,检查新增的 alembic migration 是否包含破坏性操作。命中就让流水线红、要求人工 approve。

```bash
#!/usr/bin/env bash
set -euo pipefail

# 取出本次 push 新增的 migration 文件
NEW_MIGRATIONS=$(git diff --name-only --diff-filter=A "${BASE_SHA:-HEAD~1}" "${HEAD_SHA:-HEAD}" -- 'backend/alembic/versions/*.py' || true)

if [ -z "$NEW_MIGRATIONS" ]; then
    echo "[check] 无新增 migration"
    exit 0
fi

DANGEROUS_PATTERNS='op\.drop_column|op\.drop_table|op\.execute.*DROP|op\.execute.*TRUNCATE|op\.alter_column.*type_=|op\.execute.*DELETE'

UNSAFE=0
for f in $NEW_MIGRATIONS; do
    if grep -E "$DANGEROUS_PATTERNS" "$f" > /dev/null 2>&1; then
        echo "[check] ⚠️  $f 含破坏性操作:"
        grep -nE "$DANGEROUS_PATTERNS" "$f"
        UNSAFE=1
    fi
done

if [ "$UNSAFE" -eq 1 ]; then
    echo ""
    echo "[check] 检测到破坏性迁移,自动部署已拦截。"
    echo "[check] 如确认数据可丢弃,请在 PR title 加 [allow-destructive-migration] 标记,或手动 ssh 到 ECS 跑 deploy。"
    exit 1
fi

echo "[check] 所有 migration 安全"
```

---

## 十、GitHub Actions

文件:`.github/workflows/deploy.yml`

```yaml
name: Deploy to ECS

on:
  push:
    branches: [main]
  workflow_dispatch:  # 允许手动触发

concurrency:
  group: deploy-production
  cancel-in-progress: false  # 部署期间不取消,等当前跑完

jobs:
  check-migration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: 检查破坏性迁移
        env:
          BASE_SHA: ${{ github.event.before }}
          HEAD_SHA: ${{ github.sha }}
        run: |
          # 允许 PR title / commit msg 含 [allow-destructive-migration] 跳过
          if git log -1 --pretty=%s | grep -q '\[allow-destructive-migration\]'; then
            echo "明确授权破坏性迁移,跳过检查"
            exit 0
          fi
          bash deploy/check-migration-safety.sh

  deploy:
    needs: check-migration
    runs-on: ubuntu-latest
    steps:
      - name: SSH 到 ECS 触发部署
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.ECS_HOST }}
          username: ${{ secrets.ECS_USER }}
          key: ${{ secrets.ECS_SSH_KEY }}
          port: 22
          script_stop: true
          script: |
            cd /opt/overseas-platform
            bash deploy/deploy.sh

      - name: 部署成功通知
        if: success()
        run: echo "✅ 部署完成 → http://${{ secrets.ECS_HOST }}:3000"
```

**所需 GitHub Secrets**(首次配置一次):

| Secret | 值 |
|---|---|
| `ECS_HOST` | ECS 公网 IP |
| `ECS_USER` | ECS 登录用户(如 `root` 或专用部署账号) |
| `ECS_SSH_KEY` | 私钥内容(对应 ECS 上 `~/.ssh/authorized_keys` 中的公钥) |

---

## 十一、CLAUDE.md 同步更新

修改文件:`CLAUDE.md`

### 11.1 删除原"不允许引入的依赖"中的 Docker 禁令

原内容:
```
- ❌ Docker / 容器化
```

**删除该行**。

### 11.2 新增「部署架构」章节(放在「常用命令」之后)

新增内容:

```markdown
## 部署架构

### 本地开发(不变,不要用 Docker 跑开发)

- 后端:`cd backend && uvicorn app.main:app --reload --port 8000`
- 前端:`cd frontend && pnpm dev`
- 数据库:本机 brew PostgreSQL @5433

### 演示 / 生产部署(Docker)

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | 生产容器编排(db + backend + frontend) |
| `backend/Dockerfile` | 多阶段构建,uv 装依赖,非 root 运行 |
| `frontend/Dockerfile` | 多阶段构建,pnpm + Next.js standalone |
| `backend/docker-entrypoint.sh` | 等 DB → alembic upgrade → seed → 启动 |
| `deploy/deploy.sh` | ECS 上由 CI 触发的部署脚本 |
| `deploy/check-migration-safety.sh` | CI 拦截破坏性迁移 |
| `.github/workflows/deploy.yml` | push main → 自动部署 |
| `.env.production` | ECS 上维护,**不入 Git** |
| `.env.production.example` | 入 Git 的模板 |

### 部署触发链路

```
本地 git push origin main
       ↓
GitHub Actions: check-migration → SSH 到 ECS → bash deploy/deploy.sh
       ↓
ECS: pg_dump 备份 → git pull → docker compose up -d --build → 健康检查
```

### 数据持久化约束(必须遵守)

- ✅ DB 数据落在 named volume `overseas_platform_pgdata`
- ✅ 每次部署前自动 `pg_dump`,留 7 天
- ❌ **严禁** 在任何脚本 / CI / 文档里出现 `docker compose down -v`、`docker volume rm`、`docker system prune --volumes`
- ❌ **严禁** entrypoint 跑 `alembic downgrade` / `drop` / `truncate`
- ❌ **严禁** seed.py 用 `delete + insert` 模式,必须先查后写

### 镜像与日志约束(必须遵守)

- ✅ 所有镜像 tag **精确到 minor**(如 `postgres:16.4-alpine`、`node:20.18-alpine`、`python:3.11.10-slim`)
- ✅ 升级 base 镜像必须显式提 commit,不接受浮动 tag 漂移
- ✅ 所有服务挂 `logging` 限制:`max-size: 10m`、`max-file: 3`
- ✅ Dockerfile 内 apt 源换阿里云、PyPI 源换阿里云、npm registry 换淘宝镜像(国内 build 必备)
- ❌ **严禁** 用 `pnpm@latest` / `node:20-alpine` / `:latest` / 任何浮动 tag

### 迁移安全

- 新增 migration 含 `drop_column` / `drop_table` / `alter_column type_=` / 任何 `DROP|TRUNCATE|DELETE` 的 raw SQL → CI 自动拦截
- 确实需要执行 → commit message 加 `[allow-destructive-migration]` 标记,且**手动 SSH 到 ECS** 跑,不允许走自动部署

### 不允许做的事

- ❌ 用 Docker 跑本地开发(慢,失去 reload 体验)
- ❌ 在 docker-compose.yml 里写死 secret
- ❌ 把 `.env.production` 提交进 Git
- ❌ 在 backend Dockerfile 用 npm / 在 frontend Dockerfile 用 npm(锁定栈是 uv + pnpm)
- ❌ 引入 K8s / Swarm / 镜像 registry(单机 compose 够用)
- ❌ 引入 Nginx / HTTPS / 域名(MVP 阶段公网 IP 直连)
```

### 11.3 修改「常用命令」末尾,新增 Docker 子节

在「### 前端」后面追加:

```markdown
### Docker(部署专用,本地开发不用)

```bash
# 本地预览生产镜像(可选,debug 用)
cp .env.production.example .env.production  # 填实际值
docker compose --env-file .env.production up -d --build

# ECS 上手动触发部署(应急,平时走 GitHub Actions)
ssh user@<ECS-IP>
cd /opt/overseas-platform
bash deploy/deploy.sh

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend

# 进入容器
docker compose exec backend bash
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB

# 备份 / 恢复
docker compose exec -T db pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > backup.sql.gz
gunzip -c backup.sql.gz | docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
```
```

---

## 十二、清理旧演示文件

单独一个 commit,删除以下文件(均为之前演示包遗留):

- `package-for-delivery.sh`
- `start.command`
- `stop.command`
- `docker-compose.override.yml`(如存在)
- `docs/部署指南.md`(原演示版,会被新的 `deploy/README.md` 取代)

---

## 十三、部署 README

文件:`deploy/README.md`

写**首次部署 checklist**(给以后的自己 / 同事看):

```markdown
# 部署指南

## 首次部署(只做一次)

### 1. ECS 准备

- [ ] ECS 已装 Docker + Docker Compose(参考阿里云镜像加速配置)
- [ ] ECS 安全组开放 22 / 3000 / 8000 端口
- [ ] ECS 创建部署目录:`sudo mkdir -p /opt/overseas-platform && sudo chown $USER:$USER /opt/overseas-platform`

### 2. SSH 密钥配置

- [ ] 本地生成专用部署密钥(或复用已有):`ssh-keygen -t ed25519 -f ~/.ssh/ecs_deploy -C "github-actions-deploy"`
- [ ] 公钥追加到 ECS 的 `~/.ssh/authorized_keys`
- [ ] 私钥内容存到 GitHub Secrets:`ECS_SSH_KEY`
- [ ] ECS 公网 IP 存到 GitHub Secrets:`ECS_HOST`
- [ ] ECS 用户名存到 GitHub Secrets:`ECS_USER`

### 3. 首次 clone + env

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
git clone <repo-url> .
cp .env.production.example .env.production
vim .env.production  # 填入真实值
chmod 600 .env.production
```

### 4. 首次启动

```bash
bash deploy/deploy.sh
```

### 5. 改 super admin 密码

访问 `http://<ECS-IP>:3000`,用 `.env.production` 里的 `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_INITIAL_PASSWORD` 登录,**立即改密**。

---

## 日常部署

不需要做任何事,`git push origin main` 即可。GitHub Actions 会自动跑。

查看部署状态:GitHub repo → Actions tab。

---

## 应急

### 自动部署失败 → 手动重试

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
bash deploy/deploy.sh
```

### 回滚到上一版本

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
git log --oneline -10              # 找到上一版 commit
git reset --hard <commit-sha>
bash deploy/deploy.sh
```

### 数据库恢复

```bash
ssh user@<ECS-IP>
cd /opt/overseas-platform
ls backups/                        # 找最近的备份
gunzip -c backups/YYYYMMDD-HHMMSS.sql.gz | \
    docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
```
```

---

## 验收标准

实施完成后必须满足:

### 功能性

- [ ] 本地 `docker compose --env-file .env.production up -d --build` 能起来,前端能登录,后端 API 正常
- [ ] `docker compose down`(注意没有 `-v`)后再 `up -d`,数据仍在
- [ ] `docker compose up -d --build`(重建镜像)后,DB 数据仍在
- [ ] 关掉容器、删掉镜像、`docker compose up -d --build` 重来,DB 数据仍在(volume 保留)
- [ ] seed.py 跑两次没有重复数据 / 没报唯一键冲突
- [ ] alembic 迁移幂等(`upgrade head` 跑两次不报错)

### 自动化

- [ ] `git push origin main` 触发 GitHub Actions
- [ ] Actions 跑 check-migration → SSH → deploy.sh 全流程绿
- [ ] 部署完成后,curl ECS 公网 IP:8000/healthz 返回 200
- [ ] 部署完成后,浏览器访问 ECS 公网 IP:3000 能登录

### 安全约束

- [ ] 仓库内 grep `docker compose down -v` → 无命中
- [ ] 仓库内 grep `docker volume rm` → 无命中
- [ ] `.gitignore` 含 `.env.production` 且 `git status` 显示其被忽略
- [ ] 包含 `op.drop_column` 的测试 migration 能被 check-migration-safety.sh 拦下

### 文档

- [ ] CLAUDE.md 已删除 Docker 禁令
- [ ] CLAUDE.md 新增「部署架构」章节
- [ ] `deploy/README.md` 含首次部署 checklist
- [ ] `.env.production.example` 含所有需要的变量

---

## 风险点 & 注意事项

1. **首次部署需要人工**:配 GitHub Secrets、SSH key、.env.production 这几步无法自动化,文档里要写清。
2. **NEXT_PUBLIC_API_BASE_URL 必须 build 时注入**:这是 client 包变量,运行时改不了。如果 ECS IP 变了,需要重 build 镜像。
3. **pg_dump 备份不是无限保留**:7 天滚动,长期备份需另外处理(本次不做)。
4. **CI 跑 SSH 部署需要 ECS 网络可达**:GitHub Actions 是境外 IP,需要 ECS 安全组允许 GitHub Actions 的 IP 段 / 或者直接放开 22 端口给 0.0.0.0(MVP 阶段可接受,后续可加白名单)。
5. **首次切换需要迁移老演示数据**:因为 named volume 名字从默认变成 `overseas_platform_pgdata`,Docker 认为是新卷,老数据不会自动出现。**领导可能正在使用,必须迁移**,见下方「首次部署迁移流程」。

---

## 实施顺序(给执行者参考)

### 第 0 步:前置准备(关键,昨天踩坑的根因都在这步)

1. **切到 main,确认干净**:
   ```bash
   git checkout main && git pull && git status
   ```

2. **新建分支**:
   ```bash
   git checkout -b feat/docker-deploy
   ```

3. **生成 lock 文件并 commit**(当前仓库都没有):
   ```bash
   cd backend && uv lock && cd ..
   cd frontend && pnpm install && cd ..
   git add backend/uv.lock frontend/pnpm-lock.yaml
   ```

4. **确认本地 pnpm 版本**,后续 Dockerfile 的 `corepack prepare pnpm@X.Y.Z` 用这个版本:
   ```bash
   pnpm --version    # 记下输出值,如 9.12.0
   ```
   同时把 `frontend/package.json` 顶层加 `"packageManager": "pnpm@9.12.0"`。

5. **从老 ECS 备份现有演示数据**(领导可能在用,必备):
   ```bash
   ssh user@<ECS-IP>
   cd <老演示目录>
   docker compose exec -T <老 db 服务名> pg_dump -U <老 user> <老 db> | gzip > /tmp/legacy-demo.sql.gz
   exit
   scp user@<ECS-IP>:/tmp/legacy-demo.sql.gz ./legacy-demo.sql.gz
   ```
   留着,新环境起来后 restore 进去。

### 第 1 步:后端容器化

6. 写 `backend/Dockerfile`(注意 apt 源换阿里云,uv 不走 ghcr)
7. 写 `backend/docker-entrypoint.sh`(chmod +x)
8. 写 `backend/.dockerignore`
9. 改 `backend/app/seed.py` 为幂等(每个 seed 函数先查后写)

### 第 2 步:前端容器化

10. 改 `frontend/next.config.mjs`,加 `output: 'standalone'`
11. 写 `frontend/Dockerfile`(注意 pnpm 版本锁定到本地实际版本)
12. 写 `frontend/.dockerignore`

### 第 3 步:编排

13. 写 `docker-compose.yml`(注意 named volume + logging anchor + minor tag)
14. 写 `.env.production.example`
15. 改根目录 `.gitignore`,加 `.env.production`、`.env`、`.env.local`

### 第 4 步:本地验证(关键!)

16. 本地建一个 `.env.production`(用本地 IP 或 `localhost`),跑:
    ```bash
    docker compose --env-file .env.production up -d --build
    ```
17. 验证:
    - DB / backend / frontend 三个容器都 healthy
    - 浏览器访问 localhost:3000,能登录(用 super admin)
    - `docker compose down`(无 `-v`)后 `up -d`,数据仍在
18. **不通过不进入下一步**。Dockerfile 的问题在本地解决比在 ECS 上调成本低 100 倍。

### 第 5 步:部署脚本 + CI

19. 写 `deploy/deploy.sh` + `deploy/check-migration-safety.sh`
20. 写 `deploy/README.md`(首次部署 checklist + 迁移老数据步骤)
21. 写 `.github/workflows/deploy.yml`

### 第 6 步:文档同步

22. 改 `CLAUDE.md`(删 Docker 禁令 + 加部署章节 + 加约束清单)
23. 删除旧演示文件:`package-for-delivery.sh` / `start.command` / `stop.command` / `docker-compose.override.yml` / 旧的 `docs/部署指南.md`

### 第 7 步:首次部署 + 数据迁移

24. ECS 上准备新部署目录:
    ```bash
    ssh user@<ECS-IP>
    sudo mkdir -p /opt/overseas-platform
    sudo chown $USER:$USER /opt/overseas-platform
    cd /opt/overseas-platform
    git clone <repo-url> .
    git checkout feat/docker-deploy   # 临时,合并后切回 main
    cp .env.production.example .env.production
    vim .env.production    # 填真实值,公网 IP / 强密码
    chmod 600 .env.production
    ```

25. 把第 0 步的 `legacy-demo.sql.gz` 上传到 ECS:
    ```bash
    scp legacy-demo.sql.gz user@<ECS-IP>:/opt/overseas-platform/
    ```

26. ECS 上跑首次部署:
    ```bash
    cd /opt/overseas-platform
    bash deploy/deploy.sh
    ```

27. **数据迁移**(新 DB 起来后):
    ```bash
    # 进入 db 容器先把 seed 创的默认数据清理(否则 restore 会冲突)
    # 注意:这是首次部署专用,日常部署绝不能跑
    docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
      TRUNCATE TABLE audit_logs, user_roles, role_permissions, users, roles, permissions, supplier_organizations, buyer_organizations RESTART IDENTITY CASCADE;
    "
    gunzip -c legacy-demo.sql.gz | docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
    docker compose restart backend
    ```
    > 如果老 schema 与新 schema 不同,要先在本地用 alembic 验证能从老数据 upgrade 到 head,有冲突先手工补迁移脚本。

28. 浏览器访问 ECS 公网 IP:3000,用领导/同事的老账号验证能登录。

29. **老 demo 目录关停**(确认新环境 OK 后):
    ```bash
    cd <老演示目录>
    docker compose down    # ⚠️ 注意!没有 -v,老 volume 留着以防回滚
    ```

### 第 8 步:配置 GitHub Actions + 验证自动部署

30. 在 GitHub Repo Settings → Secrets 配:`ECS_HOST` / `ECS_USER` / `ECS_SSH_KEY`
31. 合并 PR 到 main(或直接 push 一个小改动到 feat 分支测试)
32. 看 Actions 跑完绿,curl 验证服务还在

### 第 9 步:验收

33. 跑验收标准里的全部 checklist
34. 写一段简短的部署记录(本次切换时间 / 老数据迁移结果 / 后续部署只需 git push)

---

## 给执行者的特别提示

- ⚠️ **第 0 步必须先做完才进入第 1 步**,跳步会在第 4 步本地验证时炸
- ⚠️ **第 4 步本地不通过,绝对不要传 ECS**(昨天就是直接传 ECS 才发现 apt 慢 48 分钟)
- ⚠️ **第 27 步 TRUNCATE 是首次部署专属**,deploy.sh 里绝对不能有这种操作
- ⚠️ 每个 commit 提交前 grep 一遍仓库:`grep -r "down -v\|volume rm" --include="*.sh" --include="*.yml" --include="*.yaml"`,确保没有破坏性操作
- ⚠️ 用户的全局偏好:**不要在 commit message 里加 Co-Authored-By trailer**

---

*Prompt 结束*
