// 统一的 fetch 封装。
// - 自动注入 Bearer
// - 解析后端统一响应格式 {code, message, data}
// - 透传 trace_id 用于调试

const TOKEN_KEY = "ovx_access_token";
const REFRESH_KEY = "ovx_refresh_token";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: number;
  status: number;
  traceId?: string;
  data?: unknown;

  constructor(opts: { code: number; message: string; status: number; traceId?: string; data?: unknown }) {
    super(opts.message);
    this.code = opts.code;
    this.status = opts.status;
    this.traceId = opts.traceId;
    this.data = opts.data;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** 跳过 Authorization 注入(用于登录) */
  noAuth?: boolean;
};

export async function apiRequest<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { body, noAuth, headers, ...rest } = opts;
  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };
  if (!noAuth) {
    const token = getToken();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const traceId = res.headers.get("X-Trace-Id") || undefined;

  let json: any = null;
  try {
    json = await res.json();
  } catch {
    /* 非 JSON 响应,保持 null */
  }

  if (!res.ok) {
    throw new ApiError({
      code: json?.code ?? res.status * 100,
      message: json?.message ?? res.statusText ?? "Request failed",
      status: res.status,
      traceId: json?.trace_id ?? traceId,
      data: json?.data,
    });
  }

  if (json && typeof json === "object" && "code" in json) {
    if (json.code !== 0) {
      throw new ApiError({
        code: json.code,
        message: json.message,
        status: res.status,
        traceId: json.trace_id ?? traceId,
        data: json.data,
      });
    }
    return json.data as T;
  }
  return json as T;
}

export const api = {
  get: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "POST", body }),
  put: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PUT", body }),
  patch: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "DELETE" }),
};
