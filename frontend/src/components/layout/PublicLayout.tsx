"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { PUBLIC_NAV } from "@/config/navigation";

/** 公开区 Layout(顶部单行 nav,无 sidebar)。 */
export function PublicLayout({
  children,
  noContainer = false,
}: {
  children: ReactNode;
  /** 关闭内置 max-w/padding,适合首页等需要全屏 hero 的场景 */
  noContainer?: boolean;
}) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader centerNav={<PublicNav pathname={pathname} />} />
      {noContainer ? (
        <main>{children}</main>
      ) : (
        <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
      )}
    </div>
  );
}

function PublicNav({ pathname }: { pathname: string }) {
  return (
    <nav className="flex items-center gap-1" aria-label="主导航">
      {PUBLIC_NAV.map((item) => {
        // 子路径也算激活(如 /mall/xxx 时高亮"严选商城")
        const active =
          item.path === "/"
            ? pathname === "/"
            : pathname === item.path || pathname.startsWith(item.path + "/");
        return (
          <Link
            key={item.path}
            href={item.path}
            className={
              "relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-200 " +
              (active
                ? "text-[#003366]"
                : "text-gray-500 hover:bg-slate-50 hover:text-[#003366]")
            }
          >
            <span className="block text-center leading-tight">
              <span className="block">{item.label}</span>
              {item.labelEn && (
                <span className="-mt-0.5 block text-[8px] font-normal text-gray-400">
                  {item.labelEn}
                </span>
              )}
            </span>
            {active && (
              <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-[#FF6B35]" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
