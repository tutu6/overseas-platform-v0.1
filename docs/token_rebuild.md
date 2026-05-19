# Token 存储重构:Refresh → httpOnly Cookie,Access → 内存

## 背景

当前实现:access_token 和 refresh_token 都存 `localStorage`,XSS 攻击下会被窃取。

目标:迁移到业界主流方案:
- **refresh_token**:存 httpOnly cookie,JS 完全读不到
- **access_token**:存内存(Zustand store),刷新页面通过 refresh cookie 静默续期

**本次改动范围严格限定在 token 存储机制**。不动 RBAC、审计、业务接口、UI 文案、其他任何无关代码。

---

## 后端改动(FastAPI)

### 1. 配置项新增

在 `app/core/config.py` 的 `Settings` 类加:

```python
# Refresh token cookie 配置
REFRESH_COOKIE_NAME: str = "refresh_token"
REFRESH_COOKIE_PATH: str = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE: int = 7 * 24 * 3600  # 7 天,与 refresh JWT TTL 一致
REFRESH_COOKIE_SECURE: bool = False  # 开发环境 False(允许 http),生产 True
REFRESH_COOKIE_SAMESITE: str = "strict"  # strict / lax / none

# CORS 允许携带凭证
CORS_ALLOW_CREDENTIALS: bool = True
CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
```

`.env.example` 同步加上这些项。

### 2. CORS 中间件调整

在 `app/main.py` 的 CORS 中间件:
- `allow_credentials=True`
- `allow_origins` 严格白名单(**不能是 `*`**,带凭证时浏览器会拒绝 `*`)
- 从 `settings.CORS_ALLOWED_ORIGINS` 读

### 3. `/auth/login` 接口改造

文件:`app/api/v1/auth.py`

改动:
- 函数签名增加 `response: Response`(FastAPI 依赖注入)
- 签发 access + refresh 后:
  - **access_token 仍在 response body 返回**
  - **refresh_token 通过 `response.set_cookie` 写入,不再返回 body**
- cookie 参数:
```python
  response.set_cookie(
      key=settings.REFRESH_COOKIE_NAME,
      value=refresh_token,
      max_age=settings.REFRESH_COOKIE_MAX_AGE,
      path=settings.REFRESH_COOKIE_PATH,
      httponly=True,
      secure=settings.REFRESH_COOKIE_SECURE,
      samesite=settings.REFRESH_COOKIE_SAMESITE,
  )
```
- Pydantic 响应 schema(`schemas/auth.py` 里的登录响应)删除 `refresh_token` 字段,只保留 `access_token` + `token_type`

### 4. 新增 `/auth/refresh` 接口

文件:`app/api/v1/auth.py`

```python
@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # 1. CSRF 防御:校验 Origin / Referer
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin or not _origin_allowed(origin, settings.CORS_ALLOWED_ORIGINS):
        raise UnauthorizedError("Invalid origin")
    
    # 2. 从 cookie 读 refresh token
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedError("No refresh token")
    
    # 3. 解码 + 校验(type 必须是 'refresh')
    try:
        payload = decode_jwt(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
        user_id = payload["sub"]
    except JWTError:
        raise UnauthorizedError("Invalid refresh token")
    
    # 4. 查 user,确认 ACTIVE
    user = await get_user_by_id(db, user_id)
    if not user or user.status != "ACTIVE":
        raise UnauthorizedError("User unavailable")
    
    # 5. 签发新 access + 新 refresh(refresh 轮转)
    new_access = create_access_token(user_id, user.email)
    new_refresh = create_refresh_token(user_id, user.email)
    
    # 6. 新 refresh 写回 cookie(轮转)
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=new_refresh,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    
    # 7. 返回新 access
    return {"access_token": new_access, "token_type": "bearer"}
```

辅助函数 `_origin_allowed(origin: str, allowed: list[str]) -> bool`:
- 提取 origin 的 scheme://host:port(去掉 path)
- 与 allowed 列表精确匹配
- referer 头要做 scheme://host:port 截取后再比

**不写入 audit_logs**(refresh 是后台静默动作,记审计会噪声爆炸)。

### 5. `/auth/logout` 接口改造

清除 refresh cookie:

```python
response.delete_cookie(
    key=settings.REFRESH_COOKIE_NAME,
    path=settings.REFRESH_COOKIE_PATH,
)
```

审计日志 LOGOUT 保留不变。

### 6. 路由注册

在 `app/api/v1/auth.py` 把 `/refresh` 加进 router。

### 7. 测试用例

`tests/` 下新增 / 调整:

- `test_auth_login`:断言响应 body 不含 refresh_token,响应头有 `Set-Cookie: refresh_token=...; HttpOnly`
- `test_auth_refresh_success`:用 login 拿到的 cookie 调 refresh,断言返回新 access + 新 cookie
- `test_auth_refresh_no_cookie`:不带 cookie 调 refresh → 401
- `test_auth_refresh_invalid_token`:带伪造 refresh → 401
- `test_auth_refresh_invalid_origin`:带正确 cookie 但 origin 不在白名单 → 401
- `test_auth_refresh_disabled_user`:用户 DISABLED → 401
- `test_auth_logout`:断言响应头有 `Set-Cookie: refresh_token=; Max-Age=0`

httpx AsyncClient 的 cookie 处理:用同一个 client 实例就能自动维持 cookie jar。

---

## 前端改动(Next.js)

### 1. Zustand authStore 重构

文件:`src/store/authStore.ts`(或当前 authStore 路径)

- 新增 `accessToken: string | null` 字段(**只在内存,不持久化到 localStorage**)
- 删除 access_token / refresh_token 的 localStorage 读写
- `user`、`loaded` 等其他字段保持不变(loaded 仍可持久,user 不持久——刷新后通过 /auth/me 重新拉)

### 2. lib/api.ts 重构

核心改动:

```typescript
// 请求拦截器
async function request(url: string, options: RequestInit = {}) {
  const accessToken = useAuthStore.getState().accessToken;
  
  const headers = new Headers(options.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",  // ← 关键:让浏览器自动带 cookie
  });
  
  // 401 自动 refresh + 重试一次
  if (response.status === 401 && !options._isRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request(url, { ...options, _isRetry: true });
    } else {
      // refresh 失败 → 跳登录
      useAuthStore.getState().clear();
      window.location.href = "/login";
      return response;
    }
  }
  
  return response;
}

// refresh 流程:防止并发请求触发多次 refresh
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return false;
      const data = await res.json();
      useAuthStore.getState().setAccessToken(data.access_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
}
```

要点:
- `credentials: "include"` 必须加,否则浏览器不带 cookie
- 401 重试机制要防递归(`_isRetry` 标志)
- 并发请求触发多次 refresh 用 promise 复用机制避免

### 3. AuthProvider / App 启动时静默续期

文件:`src/components/AuthProvider.tsx`(或对应 provider)

```typescript
useEffect(() => {
  (async () => {
    // 启动时先尝试 refresh(cookie 存在则成功,否则失败)
    const refreshed = await tryRefresh();
    if (refreshed) {
      // refresh 成功 → 拉 me
      const me = await api.get("/api/v1/auth/me");
      if (me.ok) {
        const data = await me.json();
        useAuthStore.getState().setUser(data.data);
      }
    }
    useAuthStore.getState().setLoaded(true);
  })();
}, []);
```

### 4. 登录页改造

文件:`src/app/(auth)/login/page.tsx`

- 登录成功后:
  - 从响应 body 拿 `access_token`,调 `setAccessToken(token)` 存入 Zustand
  - **不再写 localStorage**
  - cookie 由浏览器自动接收
- 后续调 `/auth/me` 流程不变

### 5. 登出流程

调 `/auth/logout` 接口(后端会清 cookie),前端再清 Zustand 内存,跳 `/login`。

### 6. 清理 localStorage 残留

全局搜索 `localStorage.getItem("access_token")`、`localStorage.getItem("refresh_token")`、`localStorage.setItem` 凡涉及 token 的全部删除。

`localStorage` 其他用途(如 `debug` 开关)保留不动。

### 7. 现有用户兼容(可选)

考虑到开发期已有用户在 localStorage 存了旧 token,app 启动时主动清一次:

```typescript
useEffect(() => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}, []);
```

跑一次后可删,或永久留着也无害。

---

## 验收清单

后端跑 pytest 全绿 + 以下端到端验证:

- [ ] 登录后浏览器 DevTools Application → Cookies 看到 `refresh_token`,HttpOnly 列勾上
- [ ] 同一处 DevTools Application → Local Storage **没有** access_token / refresh_token
- [ ] 刷新页面后用户仍登录(通过 refresh 静默续期)
- [ ] DevTools Console 执行 `document.cookie` **看不到** refresh_token(httpOnly 生效)
- [ ] 手动等 15 分钟(或临时把 access TTL 改 30s 测),触发 401 后自动 refresh + 重发,用户无感知
- [ ] 登出后 cookie 被清除,刷新页面跳 /login
- [ ] 篡改请求 Origin 头调 /auth/refresh → 401

---

## 注意事项

1. **本机开发用 http**,`REFRESH_COOKIE_SECURE=False`;生产 https 必须 `True`,否则浏览器拒发 cookie
2. **SameSite=Strict** 在某些跨子域场景会拦截 cookie,如果生产环境前后端不同域,可能要改 `Lax`。MVP 同源就用 Strict
3. **CORS_ALLOWED_ORIGINS 不能用 `*`**,必须显式列出域名,否则浏览器带凭证请求会被拒
4. **/auth/refresh 的 CSRF 防御只靠 Origin/Referer 校验**,MVP 阶段够用;未来高安全要求再加 double-submit cookie token
5. 不要在 refresh 接口里写 audit_logs(噪音太大);如果非要记,降级为 logger.info
6. 改完后 `tests/conftest.py` 如果有用 access/refresh token 的 fixture,要相应调整(refresh 从 cookie 读,不再从 body)

---

## 不要做的事

- 不要改 RBAC 配置、权限矩阵、scope 逻辑
- 不要改 audit_logs 表结构、写入逻辑(除 logout 保持不变外)
- 不要改业务接口(admin/users、_debug、test 等)
- 不要改 UI 文案、布局、样式
- 不要顺手"优化"任何无关代码

完成后跑 `pytest` 确保全绿,前端跑 `npm run dev` 走一遍登录 → 刷新 → 等过期 → 登出全流程。