"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/auth";
import { defaultDashboardOf } from "@/config/navigation";
import { clearTokens, getToken, setTokens } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

/**
 * 应用入口处调用一次:有 token → 拉 /auth/me,无则标记 loaded。
 */
export function useBootstrapAuth() {
  const { setUser, setLoaded, reset } = useAuthStore();

  useEffect(() => {
    const token = getToken();
    if (!token) {
      reset();
      return;
    }
    authApi
      .me()
      .then((me) => {
        setUser(me);
        setLoaded(true);
      })
      .catch(() => {
        clearTokens();
        reset();
      });
  }, [reset, setLoaded, setUser]);
}

/**
 * 登录:拿 token → 存 → 调 /me → 写 store → 按 must_change_password 跳转。
 */
export function useLogin() {
  const router = useRouter();
  const setUser = useAuthStore((s) => s.setUser);
  const setLoaded = useAuthStore((s) => s.setLoaded);

  return async (email: string, password: string) => {
    const tokens = await authApi.login(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
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

/** 登出:写审计(忽略失败)→ 清 token → 清 store → 跳 /login。 */
export function useLogout() {
  const router = useRouter();
  const reset = useAuthStore((s) => s.reset);

  return async () => {
    try {
      await authApi.logout();
    } catch {
      /* 即使后端失败也要本地登出 */
    }
    clearTokens();
    reset();
    router.replace("/login");
  };
}
