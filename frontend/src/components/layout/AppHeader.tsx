"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { LogOut, Settings, Bug, Sparkles } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { useDebugMode } from "@/stores/uiStore";
import { useLogout } from "@/hooks/useAuth";
import { BRAND } from "@/config/brand";
import type { RoleCode } from "@/lib/auth";

const ROLE_BADGE_COLOR: Record<RoleCode, string> = {
  BUYER: "#003366",
  SUPPLIER: "#FF6B35",
  OPERATOR: "#0F4C81",
  ADMIN: "#475569",
};

const ROLE_LABEL: Record<RoleCode, string> = {
  BUYER: "采购方",
  SUPPLIER: "供应商",
  OPERATOR: "平台运营",
  ADMIN: "系统管理员",
};

/** 顶部 Header(工作台 + 公开区共用)。 */
export function AppHeader({
  showDebugToggle = false,
  centerNav,
}: {
  showDebugToggle?: boolean;
  /** 中间区域插槽,公开区在此渲染主导航 */
  centerNav?: ReactNode;
}) {
  const user = useAuthStore((s) => s.user);
  const [debugMode, setDebugMode] = useDebugMode();
  const logout = useLogout();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-4 px-6">
        {/* 左:品牌 */}
        <Link href="/" className="group flex shrink-0 items-center gap-3" aria-label={`${BRAND.name} 首页`}>
          <span className="relative flex h-8 w-8 items-center justify-center rounded bg-[#003366] transition-transform duration-300 group-hover:scale-105">
            <span className="select-none text-sm font-black leading-none text-white">{BRAND.logoChar}</span>
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-[#FF6B35]" />
          </span>
          <span className="leading-none">
            <span className="block text-xl font-black tracking-tight text-[#003366]">{BRAND.name}</span>
            <span className="mt-0.5 block text-[9px] font-medium tracking-[0.15em] text-gray-400">{BRAND.nameEn}</span>
          </span>
        </Link>

        {/* 中:主导航插槽(公开区填充) */}
        {centerNav && <div className="flex flex-1 justify-center">{centerNav}</div>}

        {/* 右:调试 toggle + 用户 */}
        <div className="flex items-center gap-3">
          {showDebugToggle && (
            <button
              onClick={() => setDebugMode(!debugMode)}
              title={debugMode ? "调试模式:显示所有 tab(无权置灰)" : "线上模式:仅显示有权 tab"}
              className={
                "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors " +
                (debugMode
                  ? "border-[#FF6B35]/40 bg-[#FF6B35]/10 text-[#FF6B35]"
                  : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50")
              }
            >
              {debugMode ? <Bug className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
              {debugMode ? "调试模式" : "线上模式"}
            </button>
          )}

          {user ? (
            <>
              {user.roles.map((r) => (
                <span
                  key={r}
                  className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-white"
                  style={{ backgroundColor: ROLE_BADGE_COLOR[r] ?? "#64748b" }}
                  title={`角色:${ROLE_LABEL[r]}`}
                >
                  {r}
                </span>
              ))}
              <span className="hidden text-xs text-slate-500 sm:inline">
                {user.username || user.email}
              </span>
              <Link
                href="/account"
                title="账户设置"
                className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                <Settings className="h-4 w-4" />
              </Link>
              <button
                onClick={logout}
                title="退出登录"
                className="flex h-8 items-center gap-1 rounded-md border border-slate-200 px-2.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <LogOut className="h-3.5 w-3.5" /> 退出
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-[#003366] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#002244]"
            >
              登录
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
