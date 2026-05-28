"use client";

import useSWR from "swr";

import { catalogApi, type CatalogCardOut } from "@/lib/api/catalog";

/**
 * 按品类编码拉资料卡(GET /api/v1/catalog/cards/{code})。
 *
 * 资料卡是慢变内容,无需自动 revalidate;无权限(SUPPLIER/ADMIN)/
 * 未登录时,apiRequest 会抛 ApiError,error 传出由调用方处理。
 */
export function useCatalogCard(categoryCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<CatalogCardOut>(
    categoryCode ? `/api/v1/catalog/cards/${categoryCode}` : null,
    () => catalogApi.getCard(categoryCode as string),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
    }
  );

  return {
    card: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
