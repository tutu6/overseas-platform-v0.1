"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PublicLayout } from "@/components/layout/PublicLayout";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { Permissions } from "@/config/permission-matrix";
import { useCatalogCard } from "@/hooks/useCatalogCard";
import type {
  CatalogAttributeOut,
  CatalogCardCertificationOut,
  CatalogCardOut,
  CatalogCardSupplierOut,
  ConfidenceLevel,
  CostBreakdown,
  OriginItem,
  RiskItem,
} from "@/lib/api/catalog";

// ---------- 色标 ----------
const CONFIDENCE_COLOR: Record<ConfidenceLevel, string> = {
  green: "bg-emerald-500",
  yellow: "bg-yellow-400",
  amber: "bg-amber-500",
  red: "bg-red-500",
};

const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  green: "四家一致",
  yellow: "大致一致",
  amber: "数字有出入,需核实",
  red: "强实时,不可用聚合值",
};

function ConfidenceDot({ level }: { level?: ConfidenceLevel }) {
  const cls = level ? CONFIDENCE_COLOR[level] : "bg-slate-300";
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${cls}`}
      title={level ? CONFIDENCE_LABEL[level] : "未标注"}
    />
  );
}

function FieldHeader({
  num,
  title,
  confidence,
}: {
  num: number;
  title: string;
  confidence?: ConfidenceLevel;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="text-xs font-mono text-slate-400">#{num}</span>
      <ConfidenceDot level={confidence} />
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
    </div>
  );
}

function SectionCard({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      {children}
    </section>
  );
}

// ---------- 各字段渲染 ----------

function AttrChips({ attrs }: { attrs: CatalogAttributeOut[] }) {
  if (attrs.length === 0) return null;
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      {attrs.map((a) => {
        const meta =
          a.attr_type === "enum"
            ? a.values.map((v) => v.value).join(" / ")
            : `${a.min_value ?? "-"} ~ ${a.max_value ?? "-"} ${a.attr_unit ?? ""}`;
        return (
          <div
            key={a.id}
            className={`rounded-md border px-3 py-1.5 text-xs ${
              a.is_variant_axis
                ? "border-[#003366] bg-[#003366]/5 text-[#003366]"
                : "border-slate-200 bg-slate-50 text-slate-700"
            }`}
            title={meta}
          >
            <span className="font-semibold">{a.attr_name}</span>
            {a.is_variant_axis && (
              <span className="ml-1 text-[10px] font-mono text-[#FF6B35]">
                ★ 核心区分
              </span>
            )}
            <span className="ml-2 text-slate-500">{meta}</span>
          </div>
        );
      })}
    </div>
  );
}

function OriginList({ items }: { items: OriginItem[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
      {items.map((o, i) => (
        <div
          key={i}
          className="rounded-lg border border-slate-200 bg-slate-50/50 p-3"
        >
          <div className="text-sm font-semibold text-slate-900">{o.region}</div>
          <div className="mt-1 text-xs text-slate-600">{o.characteristics}</div>
          <div className="mt-1 text-xs text-slate-500">{o.fit_for}</div>
          {o.note && (
            <div className="mt-1 text-xs text-amber-700">⚠ {o.note}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function CostView({ data }: { data: CostBreakdown }) {
  return (
    <div className="space-y-3">
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-400">
          <tr className="border-b border-slate-100">
            <th className="py-2 text-left font-normal">成本项</th>
            <th className="py-2 text-left font-normal">占比</th>
            <th className="py-2 text-left font-normal">备注</th>
          </tr>
        </thead>
        <tbody className="text-slate-700">
          {data.breakdown.map((b, i) => (
            <tr key={i} className="border-b border-slate-50 last:border-b-0">
              <td className="py-2 font-medium">{b.item}</td>
              <td className="py-2">{b.ratio}</td>
              <td className="py-2 text-slate-500">{b.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
        <div>
          <span className="font-semibold text-slate-700">波动来源排序:</span>{" "}
          {data.volatility_ranking}
        </div>
        <div className="mt-1">
          <span className="font-semibold text-slate-700">铝锭价波动:</span>{" "}
          {data.aluminum_price_volatility}
        </div>
      </div>
    </div>
  );
}

function SupplierTable({ rows }: { rows: CatalogCardSupplierOut[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-400">
          <tr className="border-b border-slate-200">
            <th className="py-2 pr-3 text-left font-normal">厂商</th>
            <th className="py-2 pr-3 text-left font-normal">总部 / 产地</th>
            <th className="py-2 pr-3 text-left font-normal">规模</th>
            <th className="py-2 pr-3 text-left font-normal">主营 / 优势</th>
            <th className="py-2 pr-3 text-left font-normal">海外业绩</th>
            <th className="py-2 text-left font-normal">入驻</th>
          </tr>
        </thead>
        <tbody className="text-slate-700">
          {rows.map((s) => (
            <tr
              key={s.id}
              className="border-b border-slate-50 align-top last:border-b-0"
            >
              <td className="py-2 pr-3 font-medium">{s.supplier_name}</td>
              <td className="py-2 pr-3 text-xs text-slate-600">
                <div>{s.headquarter ?? "-"}</div>
                {s.origin && (
                  <div className="text-slate-400">{s.origin}</div>
                )}
              </td>
              <td className="py-2 pr-3 text-xs text-slate-600">{s.scale ?? "-"}</td>
              <td className="py-2 pr-3 text-xs text-slate-600">
                {s.main_products ?? "-"}
              </td>
              <td className="py-2 pr-3 text-xs text-slate-500">
                {s.overseas_track_record ?? "-"}
              </td>
              <td className="py-2 text-xs">
                {s.linked_supplier_id ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700">
                    已入驻
                  </span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">
                    渠道搜集
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CertificationTable({ rows }: { rows: CatalogCardCertificationOut[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-400">
          <tr className="border-b border-slate-200">
            <th className="py-2 pr-3 text-left font-normal">认证 / 标准</th>
            <th className="py-2 pr-3 text-left font-normal">适用市场</th>
            <th className="py-2 pr-3 text-left font-normal">来源</th>
            <th className="py-2 pr-3 text-left font-normal">可信度</th>
            <th className="py-2 pr-3 text-left font-normal">核实状态</th>
            <th className="py-2 text-left font-normal">说明</th>
          </tr>
        </thead>
        <tbody className="text-slate-700">
          {rows.map((c) => (
            <tr
              key={c.id}
              className="border-b border-slate-50 align-top last:border-b-0"
            >
              <td className="py-2 pr-3 font-medium">{c.cert_name}</td>
              <td className="py-2 pr-3 text-xs text-slate-600">
                {c.applicable_market ?? "-"}
              </td>
              <td className="py-2 pr-3 text-xs">
                {c.source === "supplier_uploaded" ? (
                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                    供应商上传
                  </span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                    渠道搜集
                  </span>
                )}
              </td>
              <td className="py-2 pr-3 text-xs text-slate-600">
                {c.credibility ?? "-"}
              </td>
              <td className="py-2 pr-3 text-xs">
                {c.verify_status === "verified" ? (
                  <span className="text-emerald-700">已核实</span>
                ) : (
                  <span className="text-slate-500">未核实</span>
                )}
              </td>
              <td className="py-2 text-xs text-slate-500">{c.note ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RiskGrid({ items }: { items: RiskItem[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {items.map((r) => (
        <div
          key={r.category}
          className="rounded-lg border border-slate-200 bg-slate-50/50 p-3"
        >
          <div className="mb-2 text-sm font-semibold text-slate-900">
            {r.category}
          </div>
          <div className="mb-2">
            <div className="text-xs font-medium text-amber-700">核心风险</div>
            <ul className="mt-1 list-disc pl-5 text-xs text-slate-700">
              {r.risks.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs font-medium text-emerald-700">防范措施</div>
            <ul className="mt-1 list-disc pl-5 text-xs text-slate-700">
              {r.controls.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- 主视图 ----------

function CatalogCardView({ card }: { card: CatalogCardOut }) {
  const cm = card.confidence_marks ?? {};
  const snap = card.snapshot_at
    ? new Date(card.snapshot_at).toISOString().slice(0, 10)
    : null;

  return (
    <div className="space-y-5">
      {/* 返回 */}
      <Link
        href="/mall"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-[#003366]"
      >
        <ArrowLeft className="h-4 w-4" />
        返回严选商城
      </Link>

      {/* 顶部 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {card.category.name_zh} 品类资料卡
            </h1>
            {card.category.name_en && (
              <p className="mt-0.5 text-sm text-slate-500">
                {card.category.name_en}
              </p>
            )}
          </div>
          <div className="text-right text-xs text-slate-500">
            <div>
              版本 <span className="font-mono text-slate-700">{card.version}</span>
            </div>
            {snap && (
              <div className="mt-0.5">
                内容快照{" "}
                <span className="font-mono text-slate-700">{snap}</span>
              </div>
            )}
          </div>
        </div>

        {/* 色标图例 */}
        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-500">色标(共识度,非正确性):</span>
          {(["green", "yellow", "amber", "red"] as ConfidenceLevel[]).map((lv) => (
            <span key={lv} className="flex items-center gap-1.5">
              <ConfidenceDot level={lv} />
              {CONFIDENCE_LABEL[lv]}
            </span>
          ))}
        </div>
      </div>

      {/* 字段 1 — 品类定义 */}
      <SectionCard>
        <FieldHeader num={1} title="品类定义与边界" confidence={cm.field_1_definition} />
        <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
          {card.field_1_definition ?? "暂无内容"}
        </p>
      </SectionCard>

      {/* 字段 2 — 核心参数 + B 层属性 chips */}
      <SectionCard>
        <FieldHeader num={2} title="核心技术参数" confidence={cm.field_2_tech_params} />
        <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
          {card.field_2_tech_params ?? "暂无内容"}
        </p>
        <div className="mt-3 text-xs text-slate-400">结构化属性维度(B 层):</div>
        <AttrChips attrs={card.attributes} />
      </SectionCard>

      {/* 字段 3 — 规格×场景 */}
      <SectionCard>
        <FieldHeader num={3} title="规格 × 应用场景" confidence={cm.field_3_spec_scene} />
        <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
          {card.field_3_spec_scene ?? "暂无内容"}
        </p>
      </SectionCard>

      {/* 字段 4 — 全球产地 */}
      <SectionCard>
        <FieldHeader num={4} title="全球主要产地分布" confidence={cm.field_4_origin} />
        {card.field_4_origin && card.field_4_origin.length > 0 ? (
          <OriginList items={card.field_4_origin} />
        ) : (
          <p className="text-sm text-slate-400">暂无内容</p>
        )}
      </SectionCard>

      {/* 字段 5 — 厂商(子表) */}
      <SectionCard>
        <FieldHeader num={5} title="全球主流厂商" confidence={cm.suppliers} />
        {card.suppliers.length > 0 ? (
          <SupplierTable rows={card.suppliers} />
        ) : (
          <p className="text-sm text-slate-400">暂无厂商条目</p>
        )}
      </SectionCard>

      {/* 字段 6 — 价格(占位) */}
      <SectionCard>
        <FieldHeader num={6} title="价格区间参考" confidence="red" />
        <div className="rounded-md border border-dashed border-red-200 bg-red-50/40 p-4 text-sm text-red-700">
          价格强实时,聚合值不可用。本期未接入实时行情 API
          (LME / SMM 等),需向供应商索取按"铝锭价基准日 + 加工费 + 表处费
          + 贸易条款 + 有效期"拆解的当日报价方可横比。
        </div>
      </SectionCard>

      {/* 字段 7 — 成本 */}
      <SectionCard>
        <FieldHeader num={7} title="成本构成" confidence={cm.field_7_cost} />
        {card.field_7_cost ? (
          <CostView data={card.field_7_cost} />
        ) : (
          <p className="text-sm text-slate-400">暂无内容</p>
        )}
      </SectionCard>

      {/* 字段 8 — 认证(子表) */}
      <SectionCard>
        <FieldHeader num={8} title="认证与标准" confidence={cm.certifications} />
        {card.certifications.length > 0 ? (
          <CertificationTable rows={card.certifications} />
        ) : (
          <p className="text-sm text-slate-400">暂无认证条目</p>
        )}
      </SectionCard>

      {/* 字段 9 — 运输 */}
      <SectionCard>
        <FieldHeader num={9} title="运输与包装" confidence={cm.field_9_logistics} />
        <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
          {card.field_9_logistics ?? "暂无内容"}
        </p>
      </SectionCard>

      {/* 字段 10 — 风险 */}
      <SectionCard>
        <FieldHeader num={10} title="风险与采购注意点" confidence={cm.field_10_risk} />
        {card.field_10_risk && card.field_10_risk.length > 0 ? (
          <RiskGrid items={card.field_10_risk} />
        ) : (
          <p className="text-sm text-slate-400">暂无内容</p>
        )}
      </SectionCard>
    </div>
  );
}

function CatalogContent({ code }: { code: string }) {
  const { card, isLoading, error } = useCatalogCard(code);

  if (isLoading && !card) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-sm text-slate-400">
        加载中…
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="rounded-xl border border-red-100 bg-red-50 p-8 text-center text-sm text-red-600">
        {error?.message || "未找到该品类资料卡"}
      </div>
    );
  }

  return <CatalogCardView card={card} />;
}

export default function CatalogCardPage() {
  const params = useParams<{ code: string }>();
  const code = Array.isArray(params?.code) ? params.code[0] : params?.code;

  if (!code) {
    return (
      <PublicLayout>
        <div className="rounded-xl border border-red-100 bg-red-50 p-8 text-center text-sm text-red-600">
          无效的品类编码
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <RouteGuard requiredPermissions={[Permissions.CATALOG_READ]}>
        <CatalogContent code={code} />
      </RouteGuard>
    </PublicLayout>
  );
}
