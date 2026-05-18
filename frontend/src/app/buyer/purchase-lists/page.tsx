"use client";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";
import { Permissions } from "@/lib/permissions";

export default function Page() {
  return (
    <RouteGuard requiredPermission={Permissions.PURCHASE_LIST_READ}>
      <PermissionPlaceholderPage />
    </RouteGuard>
  );
}
