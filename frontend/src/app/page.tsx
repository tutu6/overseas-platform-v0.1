import Link from "next/link";
import { ArrowRight, ShoppingCart, Building2, Sparkles, ShieldCheck } from "lucide-react";

// TODO(品牌): 品牌名待团队定调,占位
const BRAND_NAME = "央企海外工程供应链平台";
const BRAND_SUBTITLE = "B2B SUPPLY CHAIN PLATFORM";
const BRAND_LOGO_CHAR = "央";

const FEATURES = [
  { icon: ShoppingCart, title: "严选商城", desc: "类京东工业品的 B2B 采购前台" },
  { icon: Sparkles, title: "AI 智能体工具箱", desc: "标准问答 / 证书审查 / 报价比价 / 翻译" },
  { icon: ShieldCheck, title: "履约风控中枢", desc: "12 节点订单履约 + 风控驾驶舱" },
];

const TEST_PAGES = [
  { name: "采购方", path: "/test/buyer-only", color: "#003366" },
  { name: "供应商", path: "/test/supplier-only", color: "#FF6B35" },
  { name: "平台运营", path: "/test/operator-only", color: "#0F4C81" },
  { name: "系统管理员", path: "/test/admin-only", color: "#475569" },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* 顶部品牌区 */}
      <header className="bg-gradient-to-br from-[#003366] to-[#0F4C81] text-white">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="flex items-center gap-3">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 backdrop-blur">
              <span className="text-xl font-black">{BRAND_LOGO_CHAR}</span>
              <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[#003366] bg-[#FF6B35]" />
            </div>
            <div>
              <p className="text-[10px] tracking-[0.2em] text-white/50">{BRAND_SUBTITLE}</p>
              <p className="text-sm font-semibold">{BRAND_NAME}</p>
            </div>
          </div>

          <div className="mt-12 max-w-3xl">
            <p className="text-sm uppercase tracking-widest text-[#FF6B35]">MVP · 第一轮</p>
            <h1 className="mt-3 text-4xl font-black leading-tight sm:text-5xl">
              央企海外工程供应链平台
            </h1>
            <p className="mt-4 max-w-2xl text-base text-white/70">
              面向中国央企海外 EPC 项目的 B2B 供应链平台。本轮已交付的是认证 / RBAC / 审计底座,
              业务模块将在后续 prompt 中陆续上线。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
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
            </div>
          </div>
        </div>
      </header>

      {/* 三大能力 */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-4 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#003366]/10">
                <f.icon className="h-5 w-5 text-[#003366]" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-1 text-sm text-slate-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 测试页入口 */}
      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-700">RBAC 测试页(需登录对应角色)</h3>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-4">
            {TEST_PAGES.map((p) => (
              <Link
                key={p.path}
                href={p.path}
                className="group flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 transition-all hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
                  <span className="text-sm text-slate-700">{p.name}</span>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-500" />
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
