"use client";
import { ReactNode, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import type { RoleCode } from "@/lib/auth";

interface Props {
  /** 允许的角色(任一即可)。不传则只要登录即可。 */
  allowRoles?: RoleCode[];
  /** must_change_password=true 时是否强制跳改密。默认 true。 */
  enforceChangePassword?: boolean;
  children: ReactNode;
}

/**
 * 客户端路由守卫(包裹受保护页面)。
 * - loaded=false:渲染 null(避免闪烁)
 * - 未登录:跳 /login
 * - must_change_password:跳 /change-password
 * - 角色不在 allowRoles:跳默认登陆页(简单展示空白)
 */
export function RouteGuard({ allowRoles, enforceChangePassword = true, children }: Props) {
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
      router.replace("/");
    }
  }, [user, loaded, allowRoles, enforceChangePassword, pathname, router]);

  if (!loaded) return null;
  if (!user) return null;
  if (enforceChangePassword && user.must_change_password && pathname !== "/change-password") return null;
  if (allowRoles && !allowRoles.some((r) => user.roles.includes(r))) return null;

  return <>{children}</>;
}
