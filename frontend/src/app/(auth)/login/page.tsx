"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";

import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";

function LoginContent() {
  const params = useSearchParams();
  const justRegistered = params.get("registered") === "1";
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const login = useLogin();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier || !password) {
      setError("请填写用户名/邮箱和密码");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await login(identifier, password);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError("登录失败次数过多,账户已临时锁定,请 5 分钟后重试");
        } else if (err.status === 401) {
          setError("用户名/邮箱或密码错误,请重试");
        } else {
          setError(err.message || "登录失败");
        }
      } else {
        setError("网络错误,请稍后再试");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="mb-7 text-center">
        <h2 className="text-xl font-bold text-gray-900">欢迎回来</h2>
        <p className="mt-1 text-sm text-gray-400">登录您的账户继续使用</p>
      </div>

      {justRegistered && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-[#10B981] bg-[#10B981]/10 px-4 py-3 text-sm text-[#047857]">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>注册成功,请使用账号密码登录</span>
        </div>
      )}

      {error && (
        <div className="mb-5 flex items-center gap-2.5 rounded-lg border-l-4 border-red-500 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="identifier" className="text-sm font-semibold text-gray-700">
            用户名 / 邮箱
          </Label>
          <input
            id="identifier"
            type="text"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="输入用户名或邮箱"
            autoComplete="username"
            required
            className="w-full h-12 px-4 rounded-lg border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-[#FF6B35] focus:ring-2 focus:ring-[#FF6B35]/15 transition-all"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
            密码
          </Label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              autoComplete="current-password"
              required
              className="w-full h-12 px-4 pr-12 rounded-lg border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-[#FF6B35] focus:ring-2 focus:ring-[#FF6B35]/15 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#003366] text-base font-semibold text-white shadow-sm transition-all hover:bg-[#002244] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-70"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              登录中...
            </>
          ) : (
            "登录"
          )}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-sm text-gray-500">
          还没有账户?{" "}
          <Link href="/register" className="font-semibold text-[#FF6B35] transition-colors hover:text-[#e05a25]">
            立即注册
          </Link>
        </p>
      </div>

      <div className="mt-4 text-center">
        <Link href="/" className="text-xs text-gray-400 transition-colors hover:text-gray-600">
          返回首页
        </Link>
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-[#003366]" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
