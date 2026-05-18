"use client";
import { ReactNode, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import type { RoleCode } from "@/lib/auth";
import type { PermissionCode } from "@/lib/permissions";

interface Props {
  /** 允许的角色(任一即可)。不传则只要登录即可。 */
  allowRoles?: RoleCode[];
  /** 要求拥有的权限点(若用户无此权限点 → 跳 /no-permission)。 */
  requiredPermission?: PermissionCode;
  /** must_change_password=true 时是否强制跳改密。默认 true。 */
  enforceChangePassword?: boolean;
  children: ReactNode;
}

/**
 * 客户端路由守卫(包裹受保护页面)。
 * 顺序:loaded → 未登录 → 强制改密 → 角色限制 → 权限点限制 → 通过
 *
 * 注意:这是 UX 层防护,后端 require_permission 才是安全底线。
 */
export function RouteGuard({
  allowRoles,
  requiredPermission,
  enforceChangePassword = true,
  children,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loaded } = useAuthStore();

  useEffect(() => {
    if (!loaded) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (enforceChangePassword && user.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
      return;
    }
    if (allowRoles && !allowRoles.some((r) => user.roles.includes(r))) {
      router.replace(
        `/no-permission?reason=role&route=${encodeURIComponent(pathname)}`
      );
      return;
    }
    if (requiredPermission && !user.permissions.includes(requiredPermission)) {
      router.replace(
        `/no-permission?required=${encodeURIComponent(requiredPermission)}&route=${encodeURIComponent(pathname)}`
      );
    }
  }, [user, loaded, allowRoles, requiredPermission, enforceChangePassword, pathname, router]);

  if (!loaded) return null;
  if (!user) return null;
  if (enforceChangePassword && user.must_change_password && pathname !== "/change-password") return null;
  if (allowRoles && !allowRoles.some((r) => user.roles.includes(r))) return null;
  if (requiredPermission && !user.permissions.includes(requiredPermission)) return null;

  return <>{children}</>;
}
