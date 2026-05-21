import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

export const metadata: Metadata = {
  // TODO(品牌): 品牌名待团队定调,先用占位"基建严选"
  title: "基建严选 - 央企海外EPC供应链平台",
  description: "面向中国央企海外 EPC 项目的 B2B 工业品供应链平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
