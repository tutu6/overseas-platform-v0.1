"use client";
import { usePathname } from "next/navigation";
import {
  AlertCircle,
  CheckCircle2,
  type LucideIcon,
  ChevronRight,
  Sparkles,
} from "lucide-react";

import { useAuthStore } from "@/stores/authStore";
import { findNavItemByPath } from "@/config/navigation";
import type { PermissionCode } from "@/lib/permissions";

interface Props {
  /** 用于反查 navigation 配置(默认从当前 pathname 读取)。 */
  pathOverride?: string;
  /** 覆盖配置中的标题(可选)。 */
  title?: string;
  /** 覆盖描述(可选)。 */
  description?: string;
  /** 模块标签,默认从 workspace 推断。 */
  moduleLabel?: string;
  /** 要求权限点(可选,覆盖配置)。 */
  requiredPermission?: PermissionCode | null;
  /** icon override */
  icon?: LucideIcon;
}

/**
 * 占位页统一组件。
 *
 * 每个 tab 进来都长一样,展示:
 *  - 当前路由
 *  - 此页面要求的权限点
 *  - 当前用户邮箱 + 角色
 *  - 当前用户是否拥有该权限点(✅/❌)
 */
export function PermissionPlaceholderPage(props: Props = {}) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);

  const path = props.pathOverride ?? pathname;
  const navItem = findNavItemByPath(path);
  const Icon = props.icon ?? navItem?.icon ?? Sparkles;

  const title = props.title ?? navItem?.label ?? path;
  const description =
    props.description ??
    navItem?.description ??
    "(占位)此页面用于演示路由 + 侧边栏权限可视化,后续业务模块上线时替换。";

  const requiredPermission =
    props.requiredPermission !== undefined
      ? props.requiredPermission
      : navItem?.requiredPermission ?? null;

  const moduleLabel = props.moduleLabel ?? guessModule(path);

  const ok =
    requiredPermission === null ||
    (user?.permissions ?? []).includes(requiredPermission);

  const accent = ok ? "#10B981" : "#EF4444";

  return (
    <div className="space-y-4">
      {/* 标题区 */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>{moduleLabel}</span>
        <ChevronRight className="h-3.5 w-3.5" />
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
          {path}
        </code>
      </div>
      <div className="flex items-start gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
          style={{ backgroundColor: `${accent}15` }}
        >
          <Icon className="h-6 w-6" style={{ color: accent }} />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
      </div>

      {/* 权限校验卡片 */}
      <div
        className="rounded-2xl border-l-4 bg-white p-6 shadow-sm"
        style={{ borderLeftColor: accent }}
      >
        <div className="flex items-start gap-3">
          {ok ? (
            <CheckCircle2 className="mt-1 h-5 w-5 text-[#10B981]" />
          ) : (
            <AlertCircle className="mt-1 h-5 w-5 text-red-500" />
          )}
          <div className="flex-1">
            <h2 className="text-base font-semibold text-slate-900">
              {ok ? "你有权访问此页面" : "你没有此权限点"}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {ok
                ? "路由守卫与侧边栏渲染结果一致 ✓"
                : "理论上路由守卫会拦,你看到这一页说明从侧边栏调试模式硬闯进来或绕过了校验"}
            </p>
          </div>
        </div>

        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
          <InfoRow label="要求权限点">
            {requiredPermission ? (
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                {requiredPermission}
              </code>
            ) : (
              <span className="text-slate-500">公开页(无需权限)</span>
            )}
          </InfoRow>
          <InfoRow label="当前用户">
            <span className="text-slate-700">{user?.email ?? "(未登录)"}</span>
          </InfoRow>
          <InfoRow label="当前角色">
            <span className="text-slate-700">
              {user?.roles && user.roles.length > 0 ? `[${user.roles.join(", ")}]` : "(无)"}
            </span>
          </InfoRow>
          <InfoRow label="权限点检查">
            {requiredPermission === null ? (
              <span className="text-slate-500">—(公开)</span>
            ) : ok ? (
              <span className="text-[#10B981]">✅ 已拥有</span>
            ) : (
              <span className="text-red-500">❌ 缺少</span>
            )}
          </InfoRow>
        </dl>
      </div>

      {/* 占位说明 */}
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        <p className="font-medium text-slate-700">(占位)</p>
        <p className="mt-1">{description}</p>
        <p className="mt-3 text-xs text-slate-400">
          本页用于「导航 + 侧边栏 + 路由守卫」三件套的可视化验证,不实现任何业务功能。
        </p>
      </div>
    </div>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function guessModule(pathname: string): string {
  if (pathname.startsWith("/buyer")) return "BUYER 工作台";
  if (pathname.startsWith("/supplier")) return "SUPPLIER 工作台";
  if (pathname.startsWith("/operator")) return "OPERATOR 后台";
  if (pathname.startsWith("/admin")) return "ADMIN 后台";
  if (pathname.startsWith("/test")) return "RBAC 调试";
  return "公开区";
}
