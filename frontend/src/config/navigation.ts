/**
 * 单一可信源:整个平台的导航 / 侧边栏 / 占位页 / 路由守卫全部从此读取。
 *
 * 后续真业务页面替换占位时,改 navigation 的 tab 与 `requiredPermission`
 * 即可级联影响所有地方,不要在散落的地方硬编码权限点。
 */
import {
  type LucideIcon,
  AtSign,
  Building2,
  ClipboardList,
  FileBadge,
  FileText,
  Gauge,
  Globe,
  HelpCircle,
  Inbox,
  Inspect,
  KeyRound,
  LayoutDashboard,
  Package,
  Receipt,
  ScrollText,
  Send,
  Settings2,
  ShieldAlert,
  ShoppingBag,
  ShoppingCart,
  Store,
  UserCircle2,
  Users,
} from "lucide-react";

import { Permissions, type PermissionCode } from "@/lib/permissions";
import type { RoleCode } from "@/lib/auth";

export type WorkspaceCode = "BUYER" | "SUPPLIER" | "OPERATOR" | "ADMIN" | "PUBLIC";

export interface NavItem {
  /** 路由,如 `/buyer/projects` */
  path: string;
  /** 显示名 */
  label: string;
  /** icon 组件 */
  icon: LucideIcon;
  /** 要求权限点;null = 公开(已登录或未登录均可) */
  requiredPermission: PermissionCode | null;
  /** 短描述,用于占位页 + sidebar hover */
  description: string;
}

export interface NavGroup {
  /** 业务模块名,用作 sidebar 分组标题 */
  label: string;
  items: NavItem[];
}

export interface Workspace {
  code: WorkspaceCode;
  /** 顶部品牌副标 / sidebar 标题 */
  label: string;
  /** workspace 入口路径前缀,用于 sidebar 切换判定 */
  pathPrefix: string;
  /** 主题色(hex,用于区分各工作台徽章) */
  themeColor: string;
  groups: NavGroup[];
}

// =====================================================================
// 公开区(未登录可访问 + 已登录共享)
// =====================================================================

export const PUBLIC_NAV: NavItem[] = [
  {
    path: "/",
    label: "平台首页",
    icon: LayoutDashboard,
    requiredPermission: null,
    description: "平台介绍与入口",
  },
  {
    path: "/mall",
    label: "严选商城",
    icon: ShoppingBag,
    requiredPermission: null,
    description: "B2B 工业品采购前台",
  },
  {
    path: "/suppliers",
    label: "供应商目录",
    icon: Store,
    requiredPermission: null,
    description: "已入驻供应商画像与目录",
  },
  {
    path: "/countries",
    label: "国别准入",
    icon: Globe,
    requiredPermission: null,
    description: "目标出口国别的准入要求与认证",
  },
];

// =====================================================================
// 工作台
// =====================================================================

export const WORKSPACES: Workspace[] = [
  {
    code: "BUYER",
    label: "采购方工作台",
    pathPrefix: "/buyer",
    themeColor: "#003366",
    groups: [
      {
        label: "BUYER 工作台",
        items: [
          {
            path: "/buyer/dashboard",
            label: "工作台",
            icon: LayoutDashboard,
            requiredPermission: Permissions.BUYER_DASHBOARD_READ,
            description: "我的待办、概览、最近活动",
          },
          {
            path: "/buyer/projects",
            label: "项目管理",
            icon: ClipboardList,
            requiredPermission: Permissions.PROJECT_READ,
            description: "项目创建、列表、详情",
          },
          {
            path: "/buyer/purchase-lists",
            label: "采购清单",
            icon: ShoppingCart,
            requiredPermission: Permissions.PURCHASE_LIST_READ,
            description: "基于项目的采购清单管理",
          },
          {
            path: "/buyer/rfqs",
            label: "询价管理",
            icon: Send,
            requiredPermission: Permissions.RFQ_READ,
            description: "我发起的询价单与报价比较",
          },
          {
            path: "/buyer/orders",
            label: "订单管理",
            icon: Receipt,
            requiredPermission: Permissions.ORDER_READ,
            description: "订单列表 + 12 节点履约追踪",
          },
          {
            path: "/buyer/documents",
            label: "单据中心",
            icon: FileText,
            requiredPermission: Permissions.DOCUMENT_READ,
            description: "按订单查看合同 / 发票 / 提单",
          },
        ],
      },
    ],
  },
  {
    code: "SUPPLIER",
    label: "供应商工作台",
    pathPrefix: "/supplier",
    themeColor: "#FF6B35",
    groups: [
      {
        label: "SUPPLIER 工作台",
        items: [
          {
            path: "/supplier/dashboard",
            label: "工作台",
            icon: LayoutDashboard,
            requiredPermission: Permissions.SUPPLIER_DASHBOARD_READ,
            description: "待响应 RFQ、在产订单、评分总览",
          },
          {
            path: "/supplier/onboarding",
            label: "入驻向导",
            icon: FileBadge,
            requiredPermission: Permissions.SUPPLIER_ORG_WRITE,
            description: "完善企业资料与上传资质",
          },
          {
            path: "/supplier/membership",
            label: "会员中心",
            icon: KeyRound,
            requiredPermission: Permissions.MEMBERSHIP_READ,
            description: "会员状态与缴费记录",
          },
          {
            path: "/supplier/products",
            label: "商品管理",
            icon: Package,
            requiredPermission: Permissions.PRODUCT_READ,
            description: "SKU 列表 / 新增 / 国别准入资质",
          },
          {
            path: "/supplier/rfqs",
            label: "RFQ 收件箱",
            icon: Inbox,
            requiredPermission: Permissions.RFQ_RESPOND,
            description: "收到的询价单与响应详情",
          },
          {
            path: "/supplier/orders",
            label: "订单管理",
            icon: Receipt,
            requiredPermission: Permissions.ORDER_READ,
            description: "订单列表与节点打卡",
          },
          {
            path: "/supplier/profile",
            label: "我的档案",
            icon: UserCircle2,
            requiredPermission: Permissions.SUPPLIER_ORG_READ,
            description: "企业资料 / 评分查看",
          },
        ],
      },
    ],
  },
  {
    code: "OPERATOR",
    label: "运营后台",
    pathPrefix: "/operator",
    themeColor: "#0F4C81",
    groups: [
      {
        label: "OPERATOR 后台",
        items: [
          {
            path: "/operator/dashboard",
            label: "管理首页",
            icon: LayoutDashboard,
            requiredPermission: Permissions.OPERATOR_DASHBOARD_READ,
            description: "全平台数据概览",
          },
          {
            path: "/operator/supplier-review",
            label: "供应商审核",
            icon: Inspect,
            requiredPermission: Permissions.SUPPLIER_APPROVE,
            description: "入驻审批 / 评分 / 分层",
          },
          {
            path: "/operator/product-review",
            label: "商品审核",
            icon: Inspect,
            requiredPermission: Permissions.PRODUCT_APPROVE,
            description: "SKU 上架 + 国别准入资质审核",
          },
          {
            path: "/operator/orders",
            label: "订单总览",
            icon: Receipt,
            requiredPermission: Permissions.ORDER_READ_ALL,
            description: "全平台订单监控",
          },
          {
            path: "/operator/countries",
            label: "国别数据维护",
            icon: Globe,
            requiredPermission: Permissions.COUNTRY_WRITE,
            description: "8 国 × 品类准入规则维护",
          },
          {
            path: "/operator/risk-cockpit",
            label: "风控驾驶舱",
            icon: Gauge,
            requiredPermission: Permissions.RISK_READ,
            description: "马甲关系 / 价格异常 / 合规雷达(MVP 末期)",
          },
        ],
      },
    ],
  },
  {
    code: "ADMIN",
    label: "系统管理后台",
    pathPrefix: "/admin",
    themeColor: "#475569",
    groups: [
      {
        label: "ADMIN 后台",
        items: [
          {
            path: "/admin/users",
            label: "用户管理",
            icon: Users,
            requiredPermission: Permissions.USER_READ,
            description: "内部账号(ADMIN/OPERATOR)创建与停用",
          },
          {
            path: "/admin/roles",
            label: "角色管理",
            icon: ShieldAlert,
            requiredPermission: Permissions.ROLE_READ,
            description: "角色 → 权限点关系(目前由配置文件 + 启动同步管理)",
          },
          {
            path: "/admin/permissions",
            label: "权限管理",
            icon: KeyRound,
            requiredPermission: Permissions.PERMISSION_READ,
            description: "权限点清单总览",
          },
          {
            path: "/admin/config",
            label: "系统配置",
            icon: Settings2,
            requiredPermission: Permissions.SYSTEM_CONFIG,
            description: "JWT / 限流 / Trace 等系统级配置(只读展示)",
          },
        ],
      },
      {
        label: "RBAC 调试",
        items: [
          {
            path: "/test/buyer-only",
            label: "BUYER API 调试",
            icon: HelpCircle,
            requiredPermission: null, // 沿用现有逻辑(任意登录可见,内部 API 自己校验)
            description: "调用 buyer-only 后端接口验证",
          },
          {
            path: "/test/supplier-only",
            label: "SUPPLIER API 调试",
            icon: HelpCircle,
            requiredPermission: null,
            description: "调用 supplier-only 后端接口验证",
          },
          {
            path: "/test/operator-only",
            label: "OPERATOR API 调试",
            icon: HelpCircle,
            requiredPermission: null,
            description: "调用 operator-only 后端接口验证",
          },
          {
            path: "/test/admin-only",
            label: "ADMIN API 调试",
            icon: HelpCircle,
            requiredPermission: null,
            description: "调用 admin-only 后端接口验证",
          },
        ],
      },
    ],
  },
];

// =====================================================================
// 辅助:角色 → workspace 映射 + 找路由对应配置
// =====================================================================

/** 各角色默认进入的工作台 code(用于登录后跳转)。 */
export const PRIMARY_WORKSPACE_OF_ROLE: Record<RoleCode, WorkspaceCode> = {
  BUYER: "BUYER",
  SUPPLIER: "SUPPLIER",
  OPERATOR: "OPERATOR",
  ADMIN: "ADMIN",
};

/** 角色 → 默认登陆目标路径(各工作台的 dashboard / 用户管理)。 */
export function defaultDashboardOf(roles: RoleCode[]): string {
  if (roles.includes("ADMIN")) return "/admin/users";
  if (roles.includes("OPERATOR")) return "/operator/dashboard";
  if (roles.includes("SUPPLIER")) return "/supplier/dashboard";
  if (roles.includes("BUYER")) return "/buyer/dashboard";
  return "/";
}

/** 用 pathname 反查所属 workspace(用于 sidebar 当前激活)。 */
export function findWorkspaceByPath(pathname: string): Workspace | null {
  return WORKSPACES.find((w) => pathname.startsWith(w.pathPrefix)) ?? null;
}

/** 用 pathname 反查 NavItem(用于占位页统一渲染)。 */
export function findNavItemByPath(pathname: string): NavItem | null {
  for (const item of PUBLIC_NAV) {
    if (item.path === pathname) return item;
  }
  for (const w of WORKSPACES) {
    for (const g of w.groups) {
      for (const i of g.items) {
        if (i.path === pathname) return i;
      }
    }
  }
  return null;
}
