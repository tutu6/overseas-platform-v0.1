"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { useDebugMode } from "@/stores/uiStore";
import {
  PUBLIC_NAV,
  WORKSPACES,
  type NavItem,
  type Workspace,
} from "@/config/navigation";
import type { PermissionCode } from "@/lib/permissions";

/**
 * 侧边栏。
 *
 * 渲染规则:
 * - 当前 workspace 的分组全部展示
 * - 调试模式下,**其他 workspace** 的入口也展示但全部置灰(仅一行入口,不展开 tab)
 * - 公开区导航单独一组,permanent 显示
 *
 * 每个 tab 渲染:
 * - 有权:可点击,普通样式
 * - 无权 + 调试模式:置灰,hover 提示「需要 xxx 权限」
 * - 无权 + 线上模式:不渲染
 */
export function AppSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const [debugMode] = useDebugMode();

  if (!user) return null;

  const userPerms = new Set(user.permissions);
  const currentWs = WORKSPACES.find((w) => pathname.startsWith(w.pathPrefix));

  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
      <nav className="flex h-full flex-col gap-1 overflow-y-auto p-3 text-sm">
        {/* 公开区(始终显示) */}
        <SectionHeader label="公开区" />
        {PUBLIC_NAV.map((item) => (
          <NavLink
            key={item.path}
            item={item}
            currentPath={pathname}
            hasPermission={true}
            debugMode={debugMode}
          />
        ))}

        {/* 当前 workspace(完整展开) */}
        {currentWs && (
          <WorkspaceGroups
            workspace={currentWs}
            userPerms={userPerms}
            pathname={pathname}
            debugMode={debugMode}
          />
        )}

        {/* 调试模式:其他 workspace 入口(单行置灰) */}
        {debugMode && (
          <>
            <div className="mt-4 px-3 pb-1 pt-3 text-[10px] uppercase tracking-widest text-slate-400">
              其他工作台(调试模式可见)
            </div>
            {WORKSPACES.filter((w) => w.code !== currentWs?.code).map((w) => (
              <OtherWorkspaceEntry
                key={w.code}
                ws={w}
                userPerms={userPerms}
                pathname={pathname}
                debugMode={debugMode}
              />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}

function WorkspaceGroups({
  workspace,
  userPerms,
  pathname,
  debugMode,
}: {
  workspace: Workspace;
  userPerms: Set<string>;
  pathname: string;
  debugMode: boolean;
}) {
  return (
    <>
      {workspace.groups.map((g) => (
        <div key={g.label} className="mt-2">
          <SectionHeader label={g.label} accentColor={workspace.themeColor} />
          {g.items.map((item) => {
            const ok = !item.requiredPermission || userPerms.has(item.requiredPermission);
            if (!ok && !debugMode) return null;
            return (
              <NavLink
                key={item.path}
                item={item}
                currentPath={pathname}
                hasPermission={ok}
                debugMode={debugMode}
              />
            );
          })}
        </div>
      ))}
    </>
  );
}

function OtherWorkspaceEntry({
  ws,
  userPerms,
  pathname,
  debugMode,
}: {
  ws: Workspace;
  userPerms: Set<string>;
  pathname: string;
  debugMode: boolean;
}) {
  // 把 workspace 整组用一个折叠头表示(全部 tab 都列出来,置灰)
  return (
    <div className="mt-2">
      <SectionHeader label={ws.label} accentColor={ws.themeColor} muted />
      {ws.groups.map((g) =>
        g.items.map((item) => {
          const ok = !item.requiredPermission || userPerms.has(item.requiredPermission);
          return (
            <NavLink
              key={item.path}
              item={item}
              currentPath={pathname}
              hasPermission={ok}
              debugMode={debugMode}
            />
          );
        })
      )}
    </div>
  );
}

function SectionHeader({
  label,
  accentColor,
  muted = false,
}: {
  label: string;
  accentColor?: string;
  muted?: boolean;
}) {
  return (
    <div
      className={
        "mb-1 mt-2 flex items-center gap-2 px-3 text-[10px] uppercase tracking-widest " +
        (muted ? "text-slate-300" : "text-slate-400")
      }
    >
      {accentColor && (
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
      )}
      {label}
    </div>
  );
}

function NavLink({
  item,
  currentPath,
  hasPermission,
  debugMode,
}: {
  item: NavItem;
  currentPath: string;
  hasPermission: boolean;
  debugMode: boolean;
}) {
  const isActive = currentPath === item.path;
  const Icon = item.icon;
  const required = item.requiredPermission;

  // 1) 有权 → 可点击的链接
  if (hasPermission) {
    return (
      <Link
        href={item.path}
        className={
          "group flex items-center gap-2 rounded-md px-3 py-1.5 text-slate-600 transition-colors " +
          (isActive
            ? "bg-[#003366]/8 font-semibold text-[#003366]"
            : "hover:bg-slate-100 hover:text-slate-900")
        }
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate">{item.label}</span>
      </Link>
    );
  }

  // 2) 无权 + 调试模式 → 置灰 + hover 提示
  if (debugMode) {
    return (
      <div
        title={`需要权限点:${required}\n当前未拥有,在调试模式下不可点击`}
        className="group flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-1.5 text-slate-300 select-none"
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate">{item.label}</span>
        <Lock className="h-3 w-3 opacity-60" />
        <span className="hidden font-mono text-[9px] text-slate-300 group-hover:inline">
          {required}
        </span>
      </div>
    );
  }

  // 3) 无权 + 线上模式 → 不渲染(返回 null)
  return null;
}

/** 简单的 "我也用得到" 工具:从 NavItem 反推权限点 */
export function permissionOf(item: NavItem): PermissionCode | null {
  return item.requiredPermission;
}
