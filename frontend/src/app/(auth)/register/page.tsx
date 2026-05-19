"use client";
import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ChevronRight,
  Eye,
  EyeOff,
  Loader2,
  ShoppingCart,
} from "lucide-react";

import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
  validatePhoneOptional,
  validateRequired,
  validateUsc,
  validateUsernameOptional,
} from "@/lib/validators";

type Role = "BUYER" | "SUPPLIER" | "";

type FieldName =
  | "name"
  | "email"
  | "username"
  | "phone"
  | "password"
  | "confirmPassword"
  | "companyName"
  | "unifiedSocialCreditCode"
  | "businessLicenseNo";

interface FormState {
  name: string;
  email: string;
  username: string;
  phone: string;
  password: string;
  confirmPassword: string;
  companyName: string;
  unifiedSocialCreditCode: string;
  businessLicenseNo: string;
}

const initialForm: FormState = {
  name: "",
  email: "",
  username: "",
  phone: "",
  password: "",
  confirmPassword: "",
  companyName: "",
  unifiedSocialCreditCode: "",
  businessLicenseNo: "",
};

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK_BUYER =
  "border-gray-200 focus:border-[#003366] focus:ring-[#003366]/15";
const INPUT_OK_SUPPLIER =
  "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15";
const INPUT_ERR =
  "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function inputCls(role: Role, error: string | null, extra = ""): string {
  const base = error
    ? INPUT_ERR
    : role === "BUYER"
    ? INPUT_OK_BUYER
    : INPUT_OK_SUPPLIER;
  return `${INPUT_BASE} ${base} ${extra}`;
}

export default function RegisterPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("");
  const [form, setForm] = useState<FormState>(initialForm);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string | null>>>({});
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});

  /** 根据字段名跑对应的校验器。companyName / businessLicenseNo 仅在对应角色下校验。 */
  const validateField = (field: FieldName, value: string, pwd?: string): string | null => {
    switch (field) {
      case "name":
        return validateRequired(value, "姓名");
      case "email":
        return validateEmail(value);
      case "username":
        return validateUsernameOptional(value);
      case "phone":
        return validatePhoneOptional(value);
      case "password":
        return validatePassword(value);
      case "confirmPassword":
        return validatePasswordConfirm(pwd ?? form.password, value);
      case "companyName":
        return validateRequired(value, "公司名称");
      case "unifiedSocialCreditCode":
        return validateUsc(value);
      case "businessLicenseNo":
        return validateRequired(value, "营业执照号");
    }
  };

  const setField = (field: FieldName, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    // 用户继续输入,清掉该字段错误(下次 blur 再算)
    if (errors[field]) {
      setErrors((e) => ({ ...e, [field]: null }));
    }
    // password 改了,顺手清 confirmPassword 的错(避免红字滞留)
    if (field === "password" && errors.confirmPassword) {
      setErrors((e) => ({ ...e, confirmPassword: null }));
    }
  };

  const handleBlur = (field: FieldName) => {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors((e) => ({ ...e, [field]: validateField(field, form[field]) }));
  };

  const errOf = (field: FieldName): string | null =>
    touched[field] ? errors[field] ?? null : null;

  /** 提交时跑全量校验,把所有相关字段标为 touched + 错误。第一个错误用作顶部 banner。 */
  const validateAll = (): string => {
    if (!role) return "请选择注册角色";
    const fields: FieldName[] = ["name", "email", "username", "phone", "password", "confirmPassword"];
    if (role === "BUYER") fields.push("companyName", "unifiedSocialCreditCode");
    if (role === "SUPPLIER") fields.push("companyName", "businessLicenseNo");

    const newErrors: Partial<Record<FieldName, string | null>> = {};
    const newTouched: Partial<Record<FieldName, boolean>> = {};
    let firstError = "";
    for (const f of fields) {
      const err = validateField(f, form[f]);
      newTouched[f] = true;
      newErrors[f] = err;
      if (err && !firstError) firstError = err;
    }
    setTouched((t) => ({ ...t, ...newTouched }));
    setErrors((e) => ({ ...e, ...newErrors }));
    return firstError;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = validateAll();
    if (v) {
      setSubmitError(v);
      return;
    }
    setSubmitError("");
    setLoading(true);
    try {
      if (role === "BUYER") {
        await authApi.registerBuyer({
          email: form.email,
          username: form.username || undefined,
          name: form.name,
          phone: form.phone || undefined,
          password: form.password,
          company_name: form.companyName,
          unified_social_credit_code: form.unifiedSocialCreditCode,
        });
      } else {
        await authApi.registerSupplier({
          email: form.email,
          username: form.username || undefined,
          name: form.name,
          phone: form.phone || undefined,
          password: form.password,
          company_name: form.companyName,
          business_license_no: form.businessLicenseNo,
        });
      }
      // 把刚注册的凭证(优先用户名 > 手机号 > 邮箱)写入 sessionStorage,
      // /login 页 mount 时一次性消费并清掉。
      // 不走 URL:避免密码进浏览器历史/服务器日志/Referer。
      try {
        sessionStorage.setItem(
          "prefill_login",
          JSON.stringify({
            identifier: form.username || form.phone || form.email,
            password: form.password,
          })
        );
      } catch {
        // sessionStorage 可能在隐私模式被禁用;忽略,降级到无自动填充
      }
      router.replace("/login?registered=1");
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "注册失败,请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-gray-900">创建账户</h2>
        <p className="mt-1 text-sm text-gray-400">选择您的角色开始注册</p>
      </div>

      {/* 角色选择 */}
      {!role && (
        <div className="mb-6">
          <p className="mb-4 text-center text-sm text-gray-500">请选择您的角色</p>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setRole("BUYER")}
              className="group flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 p-5 transition-all hover:border-[#003366] hover:bg-[#003366]/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 transition-colors group-hover:bg-[#003366]/10">
                <ShoppingCart className="h-6 w-6 text-gray-400 transition-colors group-hover:text-[#003366]" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700 transition-colors group-hover:text-[#003366]">
                  我是采购方
                </p>
                <p className="mt-0.5 text-xs text-gray-400">央企项目部</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#003366]" />
            </button>
            <button
              type="button"
              onClick={() => setRole("SUPPLIER")}
              className="group flex flex-col items-center gap-3 rounded-xl border-2 border-gray-200 p-5 transition-all hover:border-[#FF6B35] hover:bg-[#FF6B35]/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-50 transition-colors group-hover:bg-[#FF6B35]/10">
                <Building2 className="h-6 w-6 text-gray-400 transition-colors group-hover:text-[#FF6B35]" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700 transition-colors group-hover:text-[#FF6B35]">
                  我是供应商
                </p>
                <p className="mt-0.5 text-xs text-gray-400">海外材料供货方</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-[#FF6B35]" />
            </button>
          </div>
        </div>
      )}

      {role && (
        <>
          {/* 已选角色徽标 */}
          <div
            className={
              "mb-5 flex items-center gap-3 rounded-xl p-3 " +
              (role === "BUYER" ? "bg-[#003366]/10" : "bg-[#FF6B35]/10")
            }
          >
            <div
              className={
                "flex h-8 w-8 items-center justify-center rounded-lg " +
                (role === "BUYER" ? "bg-[#003366]/20" : "bg-[#FF6B35]/20")
              }
            >
              {role === "BUYER" ? (
                <ShoppingCart className="h-4 w-4 text-[#003366]" />
              ) : (
                <Building2 className="h-4 w-4 text-[#FF6B35]" />
              )}
            </div>
            <span
              className={
                "text-sm font-semibold " +
                (role === "BUYER" ? "text-[#003366]" : "text-[#FF6B35]")
              }
            >
              {role === "BUYER" ? "采购方注册" : "供应商入驻"}
            </span>
            <button
              type="button"
              onClick={() => {
                setRole("");
                setSubmitError("");
                setErrors({});
                setTouched({});
              }}
              className="ml-auto text-xs text-gray-400 underline hover:text-gray-600"
            >
              更改角色
            </button>
          </div>

          {submitError && (
            <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* 公司信息 — 放在最上面,先识别组织再填个人信息 */}
            {role === "SUPPLIER" && (
              <>
                <Field
                  id="companyName" label="公司名称" required
                  value={form.companyName}
                  onChange={(v) => setField("companyName", v)}
                  onBlur={() => handleBlur("companyName")}
                  error={errOf("companyName")}
                  placeholder="请填写完整公司名称"
                  role={role}
                />
                <Field
                  id="businessLicenseNo" label="营业执照号" required
                  value={form.businessLicenseNo}
                  onChange={(v) => setField("businessLicenseNo", v)}
                  onBlur={() => handleBlur("businessLicenseNo")}
                  error={errOf("businessLicenseNo")}
                  placeholder="统一社会信用代码"
                  role={role}
                />
              </>
            )}

            {role === "BUYER" && (
              <>
                <Field
                  id="companyName" label="公司名称" required
                  value={form.companyName}
                  onChange={(v) => setField("companyName", v)}
                  onBlur={() => handleBlur("companyName")}
                  error={errOf("companyName")}
                  placeholder="请填写完整公司名称"
                  role={role}
                />
                <Field
                  id="unifiedSocialCreditCode" label="统一社会信用代码" required
                  hint="(18 位大写字母与数字)"
                  value={form.unifiedSocialCreditCode}
                  onChange={(v) =>
                    setField("unifiedSocialCreditCode", v.toUpperCase().slice(0, 18))
                  }
                  onBlur={() => handleBlur("unifiedSocialCreditCode")}
                  error={errOf("unifiedSocialCreditCode")}
                  placeholder="如 91110000XXXXXXXXX1"
                  maxLength={18}
                  extraInputClass="uppercase"
                  role={role}
                  footnote="系统按信用代码识别企业:首次填写将创建新组织,与已有组织信用代码相同则自动加入。"
                />
              </>
            )}

            {/* 个人信息 */}
            <div className="grid grid-cols-2 gap-3">
              <Field
                id="name" label="姓名" required
                value={form.name}
                onChange={(v) => setField("name", v)}
                onBlur={() => handleBlur("name")}
                error={errOf("name")}
                placeholder="您的姓名"
                role={role}
              />
              <Field
                id="phone" label="手机号"
                hint="(选填,可作登录凭证)"
                value={form.phone}
                onChange={(v) => setField("phone", v.replace(/\D/g, "").slice(0, 11))}
                onBlur={() => handleBlur("phone")}
                error={errOf("phone")}
                placeholder="11 位"
                inputMode="numeric"
                role={role}
              />
            </div>

            <Field
              id="email" label="邮箱地址" required type="email"
              value={form.email}
              onChange={(v) => setField("email", v)}
              onBlur={() => handleBlur("email")}
              error={errOf("email")}
              placeholder="your@email.com"
              autoComplete="email"
              role={role}
            />

            <Field
              id="username" label="用户名"
              hint="(选填,3-50 位字母/数字/下划线/短横;用于代替邮箱登录)"
              value={form.username}
              onChange={(v) => setField("username", v)}
              onBlur={() => handleBlur("username")}
              error={errOf("username")}
              placeholder="如 zhang_san"
              autoComplete="username"
              role={role}
            />

            {/* 密码 */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
                密码 * <span className="font-normal text-gray-400">(8-32 位,含字母与数字)</span>
              </Label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => setField("password", e.target.value)}
                  onBlur={() => handleBlur("password")}
                  placeholder="请输入密码"
                  autoComplete="new-password"
                  className={inputCls(role, errOf("password"), "pr-12")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errOf("password") && <p className="text-xs text-red-500">{errOf("password")}</p>}
            </div>

            {/* 确认密码 */}
            <div className="space-y-1.5">
              <Label htmlFor="confirmPassword" className="text-sm font-semibold text-gray-700">
                确认密码 *
              </Label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirm ? "text" : "password"}
                  value={form.confirmPassword}
                  onChange={(e) => setField("confirmPassword", e.target.value)}
                  onBlur={() => handleBlur("confirmPassword")}
                  placeholder="再次输入密码"
                  autoComplete="new-password"
                  className={inputCls(role, errOf("confirmPassword"), "pr-12")}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errOf("confirmPassword") ? (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
                  <AlertCircle className="h-3 w-3" /> {errOf("confirmPassword")}
                </p>
              ) : (
                form.confirmPassword &&
                form.password &&
                form.password === form.confirmPassword && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
                    <CheckCircle2 className="h-3 w-3" /> 密码匹配
                  </p>
                )
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className={
                "mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg text-base font-semibold text-white shadow-sm transition-all active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70 " +
                (role === "BUYER"
                  ? "bg-[#003366] hover:bg-[#002244]"
                  : "bg-[#FF6B35] hover:bg-[#e05a25]")
              }
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  注册中...
                </>
              ) : role === "BUYER" ? (
                "注册采购方账户"
              ) : (
                "申请供应商入驻"
              )}
            </button>
          </form>
        </>
      )}

      <div className="mt-5 text-center">
        <p className="text-sm text-gray-500">
          已有账户?{" "}
          <Link href="/login" className="font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]">
            立即登录
          </Link>
        </p>
      </div>

      <div className="mt-3 text-center">
        <Link href="/" className="text-xs text-gray-400 transition-colors hover:text-gray-600">
          返回首页
        </Link>
      </div>
    </>
  );
}

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  error: string | null;
  required?: boolean;
  hint?: string;
  footnote?: string;
  placeholder?: string;
  type?: string;
  autoComplete?: string;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  maxLength?: number;
  extraInputClass?: string;
  role: Role;
}

function Field({
  id, label, value, onChange, onBlur, error, required, hint, footnote,
  placeholder, type = "text", autoComplete, inputMode, maxLength, extraInputClass = "", role,
}: FieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm font-semibold text-gray-700">
        {label}{required && " *"}
        {hint && <span className="ml-1 font-normal text-gray-400">{hint}</span>}
      </Label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        maxLength={maxLength}
        className={inputCls(role, error, extraInputClass)}
      />
      {error ? (
        <p className="text-xs text-red-500">{error}</p>
      ) : (
        footnote && <p className="text-xs text-gray-400">{footnote}</p>
      )}
    </div>
  );
}
