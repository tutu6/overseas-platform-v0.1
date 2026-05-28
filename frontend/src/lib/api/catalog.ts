// /api/v1/catalog 客户端
//
// 后端契约见 backend/app/api/v1/catalog.py(主线一 · 品类资料卡读接口)

import { api } from "../api";

export interface CatalogCategoryOut {
  id: number;
  code: string;
  name_zh: string;
  name_en: string | null;
  display_order: number;
  status: string;
}

export interface CatalogAttributeValueOut {
  id: number;
  value: string;
  value_order: number;
}

export interface CatalogAttributeOut {
  id: number;
  attr_code: string;
  attr_name: string;
  attr_type: "enum" | "number";
  attr_unit: string | null;
  min_value: string | null; // Pydantic Decimal -> string
  max_value: string | null;
  decimal_places: number | null;
  is_filterable: boolean;
  is_variant_axis: boolean;
  display_order: number;
  values: CatalogAttributeValueOut[];
}

export interface CatalogCardSupplierOut {
  id: number;
  supplier_name: string;
  headquarter: string | null;
  origin: string | null;
  scale: string | null;
  main_products: string | null;
  overseas_track_record: string | null;
  linked_supplier_id: number | null;
  country_code: string | null;
  registration_no: string | null;
  review_status: string;
  display_order: number;
}

export interface CatalogCardCertificationOut {
  id: number;
  cert_name: string;
  applicable_market: string | null;
  source: string;
  credibility: string | null;
  verify_status: string;
  note: string | null;
  display_order: number;
}

/** 产地项(field_4_origin JSONB 内) */
export interface OriginItem {
  region: string;
  characteristics: string;
  fit_for: string;
  note?: string;
}

/** 成本结构(field_7_cost JSONB 内) */
export interface CostBreakdown {
  breakdown: Array<{ item: string; ratio: string; note: string }>;
  volatility_ranking: string;
  aluminum_price_volatility: string;
}

/** 风险项(field_10_risk JSONB 内) */
export interface RiskItem {
  category: string;
  risks: string[];
  controls: string[];
}

/** 字段级色标(confidence_marks JSONB) */
export type ConfidenceLevel = "green" | "yellow" | "amber" | "red";

export interface CatalogCardOut {
  id: number;
  category: CatalogCategoryOut;
  field_1_definition: string | null;
  field_2_tech_params: string | null;
  field_3_spec_scene: string | null;
  field_4_origin: OriginItem[] | null;
  field_7_cost: CostBreakdown | null;
  field_9_logistics: string | null;
  field_10_risk: RiskItem[] | null;
  confidence_marks: Record<string, ConfidenceLevel> | null;
  snapshot_at: string | null;
  version: string;
  review_status: string;
  attributes: CatalogAttributeOut[];
  suppliers: CatalogCardSupplierOut[];
  certifications: CatalogCardCertificationOut[];
}

export const catalogApi = {
  /** 按品类编码读完整资料卡(主表 + B 层属性 + 厂商/认证子表) */
  getCard: (categoryCode: string) =>
    api.get<CatalogCardOut>(`/api/v1/catalog/cards/${encodeURIComponent(categoryCode)}`),
};
