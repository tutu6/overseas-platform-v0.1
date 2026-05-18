"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function SuppliersDirectoryPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示供应商目录与画像。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
