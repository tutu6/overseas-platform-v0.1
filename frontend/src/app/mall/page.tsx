"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function MallPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示商城首页、品类、热门 SKU 等。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
