"use client";

// 3 步向导 Step 3:注册表单。
// - 顶部展示当前国家 + 凭证规则(只读)
// - registration_no 字段右上角徽章显示 country code(如 MY / SA)
// - 用 country.regNo.transform 规整输入(CN 自动大写截 18 位,数字国家剔除非数字)
// - blur 用 country.regNo.regex 校验
// - 密码不存任何持久化路径(useRegisterDraft 已防御)

import { useState } from "react";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";

import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth";
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirm,
  validateRegistrationNoByCountry,
  validateRequired,
  validateSupplierPhone,
} from "@/lib/validators";
import {
  getCountryByCode,
  type CountryCode,
  type LanguageCode,
} from "@/config/country-registration-rules";

type FieldName =
  | "company_name"
  | "registration_no"
  | "name"
  | "phone"
  | "email"
  | "password"
  | "confirmPassword";

interface StepFormProps {
  countryCode: CountryCode;
  languagePreference: LanguageCode;
  draft: {
    company_name: string;
    registration_no: string;
    name: string;
    phone: string;
    email: string;
  };
  updateDraft: (patch: Partial<StepFormProps["draft"]>) => void;
  onBack: () => void;
  onSubmitted: () => void;
}

const INPUT_BASE =
  "h-11 w-full rounded-lg border bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:outline-none focus:ring-2";
const INPUT_OK =
  "border-gray-200 focus:border-[#FF6B35] focus:ring-[#FF6B35]/15";
const INPUT_ERR = "border-red-400 focus:border-red-500 focus:ring-red-500/15";

function cls(err: string | null, extra = "") {
  return `${INPUT_BASE} ${err ? INPUT_ERR : INPUT_OK} ${extra}`;
}

export function StepForm({
  countryCode,
  languagePreference,
  draft,
  updateDraft,
  onBack,
  onSubmitted,
}: StepFormProps) {
  const country = getCountryByCode(countryCode);
  // password 不进 draft / sessionStorage,仅本组件 state
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string | null>>>({});
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [submitError, setSubmitError] = useState("");

  if (!country) return null;

  const validateField = (
    f: FieldName,
    value: string,
    pwd?: string,
  ): string | null => {
    switch (f) {
      case "company_name":
        return validateRequired(value, "公司名称");
      case "registration_no":
        return validateRegistrationNoByCountry(countryCode, value);
      case "name":
        return validateRequired(value, "联系人姓名");
      case "phone":
        return validateSupplierPhone(value);
      case "email":
        return validateEmail(value);
      case "password":
        return validatePassword(value);
      case "confirmPassword":
        return validatePasswordConfirm(pwd ?? password, value);
    }
  };

  const setDraftField = (f: Exclude<FieldName, "password" | "confirmPassword">, raw: string) => {
    let v = raw;
    if (f === "registration_no" && country.regNo.transform) {
      v = country.regNo.transform(raw);
    }
    updateDraft({ [f]: v });
    if (errors[f]) setErrors((e) => ({ ...e, [f]: null }));
  };

  const blur = (f: FieldName) => {
    setTouched((t) => ({ ...t, [f]: true }));
    let val: string;
    if (f === "password") val = password;
    else if (f === "confirmPassword") val = confirmPassword;
    else val = draft[f as keyof typeof draft];
    setErrors((e) => ({ ...e, [f]: validateField(f, val) }));
  };

  const errOf = (f: FieldName): string | null =>
    touched[f] ? errors[f] ?? null : null;

  const validateAll = (): string => {
    const fields: FieldName[] = [
      "company_name", "registration_no", "name", "phone", "email",
      "password", "confirmPassword",
    ];
    const newE: Partial<Record<FieldName, string | null>> = {};
    const newT: Partial<Record<FieldName, boolean>> = {};
    let first = "";
    for (const f of fields) {
      let val: string;
      if (f === "password") val = password;
      else if (f === "confirmPassword") val = confirmPassword;
      else val = draft[f as keyof typeof draft];
      const err = validateField(f, val);
      newE[f] = err;
      newT[f] = true;
      if (err && !first) first = err;
    }
    setErrors((e) => ({ ...e, ...newE }));
    setTouched((t) => ({ ...t, ...newT }));
    return first;
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateAll();
    if (err) {
      setSubmitError(err);
      return;
    }
    setSubmitError("");
    setSubmitting(true);
    try {
      await authApi.registerSupplier({
        email: draft.email,
        name: draft.name,
        phone: draft.phone,
        password,
        company_name: draft.company_name,
        country_code: countryCode,
        registration_no: draft.registration_no,
        language_preference: languagePreference,
      });
      // 注册成功 → 写预填凭证(/login 一次性消费) + 触发草稿清理与跳转
      try {
        sessionStorage.setItem(
          "prefill_login",
          JSON.stringify({
            identifier: draft.phone || draft.email,
            password,
          }),
        );
      } catch {
        // 隐私模式:降级到无自动填充
      }
      onSubmitted();
    } catch (e2) {
      setSubmitError(e2 instanceof ApiError ? e2.message : "注册失败,请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div>
        <h2 className="text-xl font-bold text-gray-900">海外供应商入驻</h2>
        <p className="mt-1 text-sm text-gray-500">请填写真实的自然人与企业组织信息</p>
      </div>

      {/* 当前国家与凭证规则提示(只读) */}
      <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
        <div className="text-sm">
          <p className="text-gray-500">
            注册地:<span className="font-semibold text-gray-800">{country.nameZh}</span> · {country.nameEn}
          </p>
          <p className="mt-0.5 text-xs text-gray-400">
            凭证:{country.regNo.label} ({country.regNo.hint})
          </p>
        </div>
        <span className="rounded bg-[#003366] px-2 py-1 text-xs font-bold tracking-wide text-white">
          {country.code}
        </span>
      </div>

      {submitError && (
        <div className="flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="company_name" className="text-sm font-semibold text-gray-700">
          公司名称 *
        </Label>
        <input
          id="company_name" name="company_name" value={draft.company_name}
          onChange={(e) => setDraftField("company_name", e.target.value)}
          onBlur={() => blur("company_name")}
          placeholder="请填写完整公司名称"
          className={cls(errOf("company_name"))}
        />
        {errOf("company_name") && <p className="text-xs text-red-500">{errOf("company_name")}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="registration_no" className="flex items-center justify-between text-sm font-semibold text-gray-700">
          <span>
            {country.regNo.label} <span className="font-normal text-gray-400">({country.regNo.hint})</span> *
          </span>
          <span className="rounded bg-[#003366]/10 px-1.5 py-0.5 font-mono text-xs font-bold text-[#003366]">
            {country.code}
          </span>
        </Label>
        <input
          id="registration_no" name="registration_no" value={draft.registration_no}
          onChange={(e) => setDraftField("registration_no", e.target.value)}
          onBlur={() => blur("registration_no")}
          placeholder={country.regNo.label}
          className={cls(errOf("registration_no"))}
        />
        {errOf("registration_no") && <p className="text-xs text-red-500">{errOf("registration_no")}</p>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="name" className="text-sm font-semibold text-gray-700">
            联系人 *
          </Label>
          <input
            id="name" name="name" value={draft.name}
            onChange={(e) => setDraftField("name", e.target.value)}
            onBlur={() => blur("name")}
            placeholder="您的姓名"
            className={cls(errOf("name"))}
          />
          {errOf("name") && <p className="text-xs text-red-500">{errOf("name")}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="phone" className="text-sm font-semibold text-gray-700">
            联系电话 *
          </Label>
          <input
            id="phone" name="phone" value={draft.phone}
            onChange={(e) => setDraftField("phone", e.target.value)}
            onBlur={() => blur("phone")}
            placeholder="如 +60 12 345 6789"
            className={cls(errOf("phone"))}
          />
          {errOf("phone") && <p className="text-xs text-red-500">{errOf("phone")}</p>}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
          联系邮箱 *
        </Label>
        <input
          id="email" name="email" type="email" value={draft.email}
          autoComplete="email"
          onChange={(e) => setDraftField("email", e.target.value)}
          onBlur={() => blur("email")}
          placeholder="your@email.com"
          className={cls(errOf("email"))}
        />
        {errOf("email") && <p className="text-xs text-red-500">{errOf("email")}</p>}
      </div>

      {/* 密码 */}
      <div className="space-y-1.5">
        <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
          输入密码 * <span className="font-normal text-gray-400">(11-50 位,需 3 类字符)</span>
        </Label>
        <div className="relative">
          <input
            id="password" name="password"
            type={showPwd ? "text" : "password"}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((er) => ({ ...er, password: null }));
              if (errors.confirmPassword) setErrors((er) => ({ ...er, confirmPassword: null }));
            }}
            onBlur={() => blur("password")}
            autoComplete="new-password"
            placeholder="请输入密码"
            className={cls(errOf("password"), "pr-12")}
          />
          <button
            type="button" tabIndex={-1}
            onClick={() => setShowPwd((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errOf("password") && <p className="text-xs text-red-500">{errOf("password")}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="confirmPassword" className="text-sm font-semibold text-gray-700">
          密码确认 *
        </Label>
        <div className="relative">
          <input
            id="confirmPassword" name="confirmPassword"
            type={showConfirm ? "text" : "password"}
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (errors.confirmPassword) setErrors((er) => ({ ...er, confirmPassword: null }));
            }}
            onBlur={() => blur("confirmPassword")}
            autoComplete="new-password"
            placeholder="再次输入密码"
            className={cls(errOf("confirmPassword"), "pr-12")}
          />
          <button
            type="button" tabIndex={-1}
            onClick={() => setShowConfirm((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errOf("confirmPassword") ? (
          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
            <AlertCircle className="h-3 w-3" /> {errOf("confirmPassword")}
          </p>
        ) : (
          confirmPassword &&
          password &&
          password === confirmPassword && (
            <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
              <CheckCircle2 className="h-3 w-3" /> 密码匹配
            </p>
          )
        )}
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="button"
          onClick={onBack}
          className="h-12 flex-1 rounded-lg border border-gray-300 bg-white text-sm font-semibold text-gray-600 transition-colors hover:bg-gray-50"
        >
          ← 返回上一步
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex h-12 flex-1 items-center justify-center gap-2 rounded-lg bg-[#FF6B35] text-sm font-semibold text-white shadow-sm transition-all hover:bg-[#e05a25] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> 提交中...
            </>
          ) : (
            "提交入驻申请"
          )}
        </button>
      </div>
    </form>
  );
}
