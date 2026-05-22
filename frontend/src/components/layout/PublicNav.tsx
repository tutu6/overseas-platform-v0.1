"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { PUBLIC_NAV } from "@/config/navigation";

/** 公开区主导航:中英双语,顶部 header 中央插槽。公开 layout 和工作台 layout 共用。 */
export function PublicNav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1" aria-label="主导航">
      {PUBLIC_NAV.map((item) => {
        // 子路径也算激活(如 /mall/xxx 时高亮"严选商城");工作台路径下全部不激活
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
