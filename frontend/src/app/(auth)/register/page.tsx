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

type Role = "BUYER" | "SUPPLIER" | "";

const PASSWORD_REGEX = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&^_\-]{8,32}$/;
// 用户名:3-50 位字母/数字/下划线/短横,且不能纯数字(与后端 USERNAME_REGEX 等价)
const USERNAME_REGEX = /^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$/;

interface FormState {
  name: string;
  email: string;
  username: string;
  phone: string;
  password: string;
  confirmPassword: string;
  companyName: string;
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
  businessLicenseNo: "",
};

export default function RegisterPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("");
  const [form, setForm] = useState<FormState>(initialForm);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const validate = (): string => {
    if (!role) return "请选择注册角色";
    if (!form.name.trim()) return "请填写姓名";
    if (!form.email.trim()) return "请填写邮箱";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return "请填写有效的邮箱地址";
    if (form.username && !USERNAME_REGEX.test(form.username))
      return "用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字";
    if (!form.password) return "请填写密码";
    if (!PASSWORD_REGEX.test(form.password)) return "密码 8-32 位,且至少包含 1 个字母和 1 个数字";
    if (form.password !== form.confirmPassword) return "两次输入的密码不一致";
    if (role === "SUPPLIER") {
      if (!form.companyName.trim()) return "请填写公司名称";
      if (!form.businessLicenseNo.trim()) return "请填写营业执照号";
    }
    return "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setError("");
    setLoading(true);
    try {
      if (role === "BUYER") {
        await authApi.registerBuyer({
          email: form.email,
          username: form.username || undefined,
          name: form.name,
          phone: form.phone || undefined,
          password: form.password,
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
      router.replace("/login?registered=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "注册失败,请稍后重试");
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
                setError("");
              }}
              className="ml-auto text-xs text-gray-400 underline hover:text-gray-600"
            >
              更改角色
            </button>
          </div>

          {error && (
            <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-sm font-semibold text-gray-700">
                  姓名 *
                </Label>
                <input
                  id="name"
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  placeholder="您的姓名"
                  required
                  className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="phone" className="text-sm font-semibold text-gray-700">
                  手机号
                </Label>
                <input
                  id="phone"
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="选填"
                  className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-semibold text-gray-700">
                邮箱地址 *
              </Label>
              <input
                id="email"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                placeholder="your@email.com"
                autoComplete="email"
                required
                className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-sm font-semibold text-gray-700">
                用户名 <span className="font-normal text-gray-400">(选填,3-50 位,字母/数字/下划线/短横;用于代替邮箱登录)</span>
              </Label>
              <input
                id="username"
                name="username"
                value={form.username}
                onChange={handleChange}
                placeholder="如 zhang_san"
                autoComplete="username"
                className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
              />
            </div>

            {role === "SUPPLIER" && (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="companyName" className="text-sm font-semibold text-gray-700">
                    公司名称 *
                  </Label>
                  <input
                    id="companyName"
                    name="companyName"
                    value={form.companyName}
                    onChange={handleChange}
                    placeholder="请填写完整公司名称"
                    required
                    className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="businessLicenseNo" className="text-sm font-semibold text-gray-700">
                    营业执照号 *
                  </Label>
                  <input
                    id="businessLicenseNo"
                    name="businessLicenseNo"
                    value={form.businessLicenseNo}
                    onChange={handleChange}
                    placeholder="统一社会信用代码"
                    required
                    className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
                  />
                </div>
              </>
            )}

            {role === "BUYER" && (
              <p className="rounded-md bg-blue-50 px-3 py-2 text-xs text-[#003366]">
                注:采购方账号默认隶属 <strong>中建三局</strong>。
              </p>
            )}

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
                  onChange={handleChange}
                  placeholder="请输入密码"
                  required
                  autoComplete="new-password"
                  className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 pr-12 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
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
            </div>

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
                  onChange={handleChange}
                  placeholder="再次输入密码"
                  required
                  autoComplete="new-password"
                  className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3 pr-12 text-sm text-gray-800 placeholder-gray-400 transition-all focus:border-[#FF6B35] focus:outline-none focus:ring-2 focus:ring-[#FF6B35]/15"
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
              {form.confirmPassword && form.password !== form.confirmPassword && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
                  <AlertCircle className="h-3 w-3" /> 两次密码不一致
                </p>
              )}
              {form.confirmPassword && form.password && form.password === form.confirmPassword && (
                <p className="mt-1 flex items-center gap-1 text-xs text-[#10B981]">
                  <CheckCircle2 className="h-3 w-3" /> 密码匹配
                </p>
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
