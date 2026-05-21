"use client";
import { PublicLayout } from "@/components/layout/PublicLayout";
import { PermissionPlaceholderPage } from "@/components/layout/PermissionPlaceholderPage";

export default function CreditPage() {
  return (
    <PublicLayout>
      <PermissionPlaceholderPage
        description="(占位)未来此页面将展示供应商信用评分、风险评估与资质认证体系。所有用户可见。"
        moduleLabel="公开区"
      />
    </PublicLayout>
  );
}
