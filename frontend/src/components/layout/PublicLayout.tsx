"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { PUBLIC_NAV } from "@/config/navigation";

/** 公开区 Layout(顶部 nav,无 sidebar)。 */
export function PublicLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader />
      <div className="border-b border-slate-200 bg-white">
        <nav className="mx-auto flex max-w-[1400px] items-center gap-1 px-6">
          {PUBLIC_NAV.map((item) => {
            const active = pathname === item.path;
            return (
              <Link
                key={item.path}
                href={item.path}
                className={
                  "flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition-colors " +
                  (active
                    ? "border-[#FF6B35] font-semibold text-[#FF6B35]"
                    : "border-transparent text-slate-600 hover:text-slate-900")
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
    </div>
  );
}
