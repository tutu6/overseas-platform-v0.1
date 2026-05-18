"use client";
import { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { RouteGuard } from "@/components/auth/RouteGuard";

/**
 * 工作台 Layout(用于 buyer / supplier / operator / admin 路由)。
 * 内部包了 RouteGuard:必须登录,且 must_change_password=true 时强制改密。
 * 精细的权限点校验由各 page 的 PermissionPlaceholderPage 内部处理。
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <RouteGuard>
      <div className="flex min-h-screen flex-col bg-slate-50">
        <AppHeader showDebugToggle />
        <div className="flex flex-1">
          <AppSidebar />
          <main className="flex-1 overflow-x-auto">
            <div className="mx-auto max-w-5xl p-6">{children}</div>
          </main>
        </div>
      </div>
    </RouteGuard>
  );
}
