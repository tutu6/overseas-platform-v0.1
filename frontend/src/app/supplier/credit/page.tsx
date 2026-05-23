"use client";
/**
 * SUPPLIER「我的信用评分」。
 *
 * 后端 SUPPLIER 调 GET /credit/companies/search 时 scope=OWN,自动只返回
 * linked_supplier_org_id = 自身的企业。
 *
 * - 列表非空:复用 BUYER 详情页 CompanyDetailView,hideAi+hideBackLink
 * - 列表为空:本期 credit_company 表无 SUPPLIER 镜像数据时的常态 → 显示"未评级"占位卡
 *
 * 业务流程 3 上线"SUPPLIER 注册→建 credit_company 镜像→触发首次评分"链路后,
 * 本页无需改动,自动切换到详情视图。
 */
import { useEffect, useState } from "react";

import { RouteGuard } from "@/components/auth/RouteGuard";
import { CompanyDetailView } from "@/components/credit/CompanyDetailView";
import { GradeBadge } from "@/components/credit/GradeBadge";
import { Permissions } from "@/config/permission-matrix";
import { useAuthStore } from "@/stores/authStore";
import { creditApi, type CompanyListItem } from "@/lib/api/credit";

const PLACEHOLDER_DIMENSIONS = [
  { name: "基础工商", max_score: 25 },
  { name: "资质认证", max_score: 25 },
  { name: "财务健康", max_score: 25 },
  { name: "司法舆情", max_score: 25 },
];

function UnratedPlaceholder() {
  const user = useAuthStore((s) => s.user);
  const orgName = user?.organization?.name ?? "本企业";

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs text-slate-400">当前评分</div>
            <h2 className="mt-1 text-2xl font-bold text-slate-900">{orgName}</h2>
          </div>
          <div className="flex flex-col items-end gap-2">
            <GradeBadge grade={null} size="lg" />
            <div className="text-right text-xs text-slate-500">
              综合得分 <span className="text-lg font-bold text-slate-900">0</span>
              <span className="text-slate-400"> / 100</span>
            </div>
          </div>
        </div>
        <div className="mt-5 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
          完成入驻流程并接收第一笔订单后,系统将自动评级。
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">四维评分</h3>
        <div className="py-8 text-center text-sm text-slate-400">尚未生成评分</div>
        <div className="mt-4 space-y-1.5">
          {PLACEHOLDER_DIMENSIONS.map((d) => (
            <div key={d.name} className="flex items-center justify-between text-xs">
              <span className="text-slate-600">{d.name}</span>
              <span className="font-medium text-slate-900">
                0 <span className="text-slate-400">/ {d.max_score}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SupplierCreditInner() {
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    creditApi
      .search({ country: "", q: "" })
      .then((items: CompanyListItem[]) => {
        setCompanyId(items.length > 0 ? items[0].id : null);
      })
      .catch(() => {
        setCompanyId(null);
      })
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">我的信用评分</h1>
        <p className="mt-1 text-sm text-slate-500">
          基建严选 · 海外工程供应商综合能力评分
        </p>
      </div>

      {!loaded ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
          加载中…
        </div>
      ) : companyId !== null ? (
        <CompanyDetailView companyId={companyId} hideAi hideBackLink />
      ) : (
        <UnratedPlaceholder />
      )}
    </div>
  );
}

export default function SupplierCreditPage() {
  return (
    <RouteGuard requiredPermissions={[Permissions.CREDIT_READ]}>
      <SupplierCreditInner />
    </RouteGuard>
  );
}
