"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { authApi } from "@/lib/auth";
import { clearTokens, tryRefresh } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";

const LEGACY_KEYS = ["ovx_access_token", "ovx_refresh_token"] as const;

function clearLegacyLocalStorage() {
  if (typeof window === "undefined") return;
  for (const k of LEGACY_KEYS) {
    try {
      localStorage.removeItem(k);
    } catch {
      /* ignore */
    }
  }
}

/**
 * 应用启动:
 *   1. 清掉旧版 localStorage token(向后兼容)
 *   2. 调 /auth/refresh —— cookie 在则成功换 access,否则失败(返回 false)
 *   3. 成功 → 拉 /auth/me 写 Zustand;失败 → 标记 loaded
 */
export function useBootstrapAuth() {
  const { setUser, setLoaded, clear } = useAuthStore();

  useEffect(() => {
    clearLegacyLocalStorage();

    (async () => {
      const refreshed = await tryRefresh();
      if (!refreshed) {
        clear();
        setLoaded(true);
        return;
      }
      try {
        const me = await authApi.me();
        setUser(me);
      } catch {
        clear();
      } finally {
        setLoaded(true);
      }
    })();
  }, [setUser, setLoaded, clear]);
}

/**
 * 登录:调 /auth/login → access 存内存 → 调 /auth/me → 按 must_change_password 跳转。
 * refresh token 由后端通过 httpOnly cookie 写入,JS 不接触。
 */
export function useLogin() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);
  const setLoaded = useAuthStore((s) => s.setLoaded);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);

  return async (identifier: string, password: string) => {
    const tokens = await authApi.login(identifier, password);
    setAccessToken(tokens.access_token);
    const me = await authApi.me();
    setUser(me);
    setLoaded(true);
    if (me.must_change_password) {
      router.replace("/change-password");
    } else {
      router.replace(defaultDashboardOf(me.roles));
    }
  };
}

/** 登出:调 /auth/logout(后端清 cookie + 写审计)→ 清内存 → 跳 /login。*/
export function useLogout() {
  const router = useRouter();
  const clear = useAuthStore((s) => s.clear);

  return async () => {
    try {
      await authApi.logout();
    } catch {
      /* 后端失败也要本地登出 */
    }
    clear();
    clearTokens(); // 兼容旧调用,内部已是清 Zustand
    router.replace("/login");
  };
}
