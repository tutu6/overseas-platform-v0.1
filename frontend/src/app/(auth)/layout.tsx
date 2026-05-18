import { ReactNode } from "react";

// TODO(品牌): 品牌名 / Logo 字母 / 副标题待团队定调,以下为占位
const BRAND_NAME = "央企海外工程供应链平台";
const BRAND_SUBTITLE = "B2B SUPPLY CHAIN PLATFORM";
const BRAND_TAGLINE = "央企海外 EPC 供应链平台";
const BRAND_LOGO_CHAR = "央"; // 占位字符,等品牌定调替换

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#003366] to-[#0F4C81] p-4">
      <div className="w-full max-w-md">
        {/* 品牌区 */}
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#003366] to-[#0F4C81] shadow-lg">
            <span className="text-2xl font-black text-white">{BRAND_LOGO_CHAR}</span>
            <span className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-[#003366] bg-[#FF6B35]" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">{BRAND_NAME}</h1>
          <p className="mt-1 text-[10px] tracking-[0.2em] text-white/40">{BRAND_SUBTITLE}</p>
          <p className="mt-2 text-sm text-white/60">{BRAND_TAGLINE}</p>
        </div>

        {/* 表单卡片 */}
        <div className="rounded-2xl border-t-4 border-[#FF6B35] bg-white p-8 shadow-xl">
          {children}
        </div>
      </div>
    </div>
  );
}
