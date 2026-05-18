"use client";
import Link from "next/link";
import { ArrowRight, ShoppingCart, Sparkles, ShieldCheck, Building2 } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { useAuthStore } from "@/stores/authStore";
import { defaultDashboardOf } from "@/config/navigation";

const FEATURES = [
  { icon: ShoppingCart, title: "严选商城", desc: "类京东工业品的 B2B 采购前台" },
  { icon: Sparkles, title: "AI 智能体工具箱", desc: "标准问答 / 证书审查 / 报价比价 / 翻译" },
  { icon: ShieldCheck, title: "履约风控中枢", desc: "12 节点订单履约 + 风控驾驶舱" },
];

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const dashboard = user ? defaultDashboardOf(user.roles) : null;

  return (
    <PublicLayout>
      {/* hero */}
      <section className="-mx-6 -mt-8 mb-8 bg-gradient-to-br from-[#003366] to-[#0F4C81] px-6 py-16 text-white">
        <div className="mx-auto max-w-4xl">
          <p className="text-sm uppercase tracking-widest text-[#FF6B35]">MVP · 第一轮</p>
          <h1 className="mt-3 text-4xl font-black leading-tight sm:text-5xl">
            央企海外工程供应链平台
          </h1>
          <p className="mt-4 max-w-2xl text-base text-white/70">
            面向中国央企海外 EPC 项目的 B2B 供应链平台。
            本轮已交付的是认证 / RBAC / 审计底座 + 完整导航 + 侧边栏可视化,业务模块在后续 prompt 中陆续上线。
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {dashboard ? (
              <Link
                href={dashboard}
                className="inline-flex h-11 items-center gap-2 rounded-lg bg-[#FF6B35] px-6 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#e05a25] active:scale-[0.99]"
              >
                进入工作台 <ArrowRight className="h-4 w-4" />
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="inline-flex h-11 items-center gap-2 rounded-lg bg-[#FF6B35] px-6 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#e05a25] active:scale-[0.99]"
                >
                  登录 <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/register"
                  className="inline-flex h-11 items-center gap-2 rounded-lg border border-white/30 bg-white/5 px-6 text-sm font-semibold text-white transition-all hover:bg-white/10 active:scale-[0.99]"
                >
                  注册账户
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      {/* features */}
      <section className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#003366]/10">
              <f.icon className="h-5 w-5 text-[#003366]" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900">{f.title}</h3>
            <p className="mt-1 text-sm text-slate-500">{f.desc}</p>
          </div>
        ))}
      </section>

      {/* 工作台 快捷入口(仅登录后显示) */}
      {user && (
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-700">你的工作台</h3>
          </div>
          <Link
            href={dashboard!}
            className="group mt-3 flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 transition-all hover:border-slate-300 hover:bg-slate-50"
          >
            <span className="text-sm text-slate-700">{dashboard}</span>
            <ArrowRight className="h-4 w-4 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-500" />
          </Link>
        </section>
      )}
    </PublicLayout>
  );
}
