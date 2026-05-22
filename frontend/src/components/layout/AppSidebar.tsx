"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock } from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { useDebugMode } from "@/stores/uiStore";
import {
  WORKSPACES,
  type NavItem,
  type Workspace,
} from "@/config/navigation";
import { scopeOf } from "@/config/permission-matrix";
import type { RoleCode } from "@/lib/auth";

/**
 * 侧边栏(v3 §8)。tab 可见性:
 *   1. 没绑 resource 且无 requiredPermissions → 一律可见
 *   2. 绑了 resource → scope=NONE 无权;否则有权
 *   3. 有 requiredPermissions(无 resource)→ 检查权限点全部满足
 *
 * 调试模式:无权置灰 + hover 提示;线上模式:无权不渲染。
 */
export function AppSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const [debugMode] = useDebugMode();

  if (!user) return null;

  const userPerms = new Set(user.permissions);
  const userRoles = user.roles as RoleCode[];
  const currentWs = WORKSPACES.find((w) => pathname.startsWith(w.pathPrefix));

  const checkAccess = (item: NavItem): { ok: boolean; reason: string } => {
    if (item.resource) {
      const scope = scopeOf(userRoles, item.resource);
      if (scope === "NONE") return { ok: false, reason: `scope=NONE on ${item.resource}` };
    }
    if (item.requiredPermissions.length > 0) {
      const missing = item.requiredPermissions.find((p) => !userPerms.has(p));
      if (missing) return { ok: false, reason: `缺权限点 ${missing}` };
    }
    return { ok: true, reason: "" };
  };

  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
      <nav className="flex h-full flex-col gap-1 overflow-y-auto p-3 text-sm">
        {currentWs && (
          <WorkspaceGroups workspace={currentWs} currentPath={pathname} debugMode={debugMode} checkAccess={checkAccess} />
        )}

        {debugMode && (
          <>
            <div className="mt-4 px-3 pb-1 pt-3 text-[10px] uppercase tracking-widest text-slate-400">
              其他工作台(调试可见)
            </div>
            {WORKSPACES.filter((w) => w.code !== currentWs?.code).map((w) => (
              <WorkspaceGroups
                key={w.code}
                workspace={w}
                currentPath={pathname}
                debugMode={debugMode}
                checkAccess={checkAccess}
                muted
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
  currentPath,
  debugMode,
  checkAccess,
  muted = false,
}: {
  workspace: Workspace;
  currentPath: string;
  debugMode: boolean;
  checkAccess: (item: NavItem) => { ok: boolean; reason: string };
  muted?: boolean;
}) {
  return (
    <>
      {workspace.groups.map((g) => (
        <div key={g.label} className="mt-2">
          <SectionHeader label={g.label} accentColor={workspace.themeColor} muted={muted} />
          {g.items.map((item) => {
            const access = checkAccess(item);
            if (!access.ok && !debugMode) return null;
            return (
              <NavLink
                key={item.path}
                item={item}
                currentPath={currentPath}
                access={access}
                debugMode={debugMode}
              />
            );
          })}
        </div>
      ))}
    </>
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
  access,
  debugMode,
}: {
  item: NavItem;
  currentPath: string;
  access: { ok: boolean; reason: string };
  debugMode: boolean;
}) {
  const isActive = currentPath === item.path;
  const Icon = item.icon;

  if (access.ok) {
    return (
      <Link
        href={item.path}
        className={
          "flex items-center gap-2 rounded-md px-3 py-1.5 text-slate-600 transition-colors " +
          (isActive
            ? "bg-[#003366]/10 font-semibold text-[#003366]"
            : "hover:bg-slate-100 hover:text-slate-900")
        }
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate">{item.label}</span>
      </Link>
    );
  }

  if (debugMode) {
    return (
      <div
        title={access.reason}
        className="flex cursor-not-allowed select-none items-center gap-2 rounded-md px-3 py-1.5 text-slate-300"
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate">{item.label}</span>
        <Lock className="h-3 w-3 opacity-60" />
      </div>
    );
  }

  return null;
}
