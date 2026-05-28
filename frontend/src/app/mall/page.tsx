"use client";

import React, { useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";

// PRD v2.0 §2.2 C5:Filter bar 国家/级别 UI 保留,纯视觉,不接后端
const countries = [
  { code: "", name: "全部国家" },
  { code: "TZ", name: "坦桑尼亚" },
  { code: "KE", name: "肯尼亚" },
  { code: "DZ", name: "阿尔及利亚" },
  { code: "SA", name: "沙特阿拉伯" },
  { code: "AE", name: "阿联酋" },
  { code: "NG", name: "尼日利亚" },
  { code: "EG", name: "埃及" },
  { code: "ZA", name: "南非" },
];

const tiers = [
  { code: "", name: "全部级别" },
  { code: "T1", name: "T1 头部" },
  { code: "T2", name: "T2 优质" },
  { code: "T3", name: "T3 认证" },
];

export default function MallPage() {
  const [selectedCountry, setSelectedCountry] = useState("");
  const [selectedTier, setSelectedTier] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const hasActiveFilters = selectedCountry || selectedTier;

  const clearAll = () => {
    setSelectedCountry("");
    setSelectedTier("");
    setSearchInput("");
  };

  return (
    <PublicLayout>
      <div className="space-y-7">
        {/* Hero */}
        <section className="rounded-2xl bg-white border border-gray-100 shadow-sm px-8 py-7">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-[#003366]">
              严选商城
              <span className="block w-12 h-1 bg-[#FF6B35] rounded-full mt-2" />
            </h1>
            <p className="text-gray-500 text-sm mt-2">
              精选全球建材供应商,严格质量认证
            </p>
          </div>
          {/* 搜索 UI 保留(PRD §1.3 不做真实搜索),form 不接 onSubmit */}
          <form
            onSubmit={(e) => e.preventDefault()}
            className="flex gap-3 max-w-2xl"
          >
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="搜索产品名称、规格、品牌..."
                className="w-full h-12 pl-12 pr-4 rounded-full border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 shadow-sm focus:outline-none focus:border-[#003366] focus:ring-2 focus:ring-[#003366]/10 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled
              className="h-12 px-7 rounded-full bg-[#003366] hover:bg-[#002244] text-white font-semibold text-sm shadow-sm transition-colors shrink-0 disabled:opacity-60 disabled:cursor-not-allowed"
              title="搜索功能开发中"
            >
              搜索
            </button>
          </form>
        </section>

        <div className="flex flex-col lg:flex-row gap-7">
          {/* Sidebar — 旧三级分类已下线,新品类资料卡导航待 Step 4 接入 */}
          <aside className="lg:w-56 shrink-0">
            <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
              <h3 className="font-semibold text-gray-800 text-sm mb-4 flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-[#003366]" />
                产品分类
              </h3>
              <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/60 px-3 py-6 text-center">
                <p className="text-sm text-gray-500">产品分类即将上线</p>
                <p className="mt-1 text-xs text-gray-400">
                  新品类资料卡导航将在后续版本接入
                </p>
              </div>
            </div>
          </aside>

          {/* Main */}
          <div className="flex-1 min-w-0 space-y-5">
            {/* Filter bar(纯视觉,PRD §2.2 C5)*/}
            <div className="bg-white rounded-2xl px-5 py-4 shadow-sm border border-gray-100 flex flex-wrap gap-3 items-center">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wide shrink-0">
                  出口国家
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {countries.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => setSelectedCountry(c.code)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                        selectedCountry === c.code
                          ? "bg-[#003366] text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="w-px h-6 bg-gray-200 hidden lg:block" />

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wide shrink-0">
                  供应商级别
                </span>
                <div className="flex gap-1.5">
                  {tiers.map((t) => (
                    <button
                      key={t.code}
                      onClick={() => setSelectedTier(t.code)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                        selectedTier === t.code
                          ? "bg-[#FF6B35] text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>

              {hasActiveFilters && (
                <button
                  onClick={clearAll}
                  className="ml-auto flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#FF6B35] transition-colors font-medium"
                >
                  <X className="h-3.5 w-3.5" />
                  清除筛选
                </button>
              )}
            </div>

            {/* 主区占位 */}
            <div className="bg-white rounded-2xl py-24 px-6 text-center border border-gray-100 shadow-sm">
              <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                <Search className="h-7 w-7 text-gray-300" />
              </div>
              <p className="text-base font-medium text-gray-600">
                商品功能开发中
              </p>
              <p className="text-sm text-gray-400 mt-2">
                品类资料卡功能将在后续版本上线
              </p>
            </div>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}
