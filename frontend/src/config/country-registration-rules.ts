// 供应商 3 步向导 · 9 国凭证规则配置(PRD v1.3 §3 / §5.3)。
//
// 边界:仅"前后端必须对齐 / 错一字即 bug"的字符串放这里。一次性展示文案直接写在
// 组件 JSX。Step 标题、副标题、字段 label、placeholder、按钮文案、Dashboard banner
// 全部硬编码在使用处。
//
// 后端对应:backend/app/constants/country_registration.py(逐字一致,手工同步)。

/** 9 国凭证规则的单条配置 */
export interface CountryRule {
  /** ISO 2 字母国家码,与后端 COUNTRY_CODES 一一对应 */
  code: CountryCode;
  nameZh: string;
  nameEn: string;
  /** 本国主语言 code(用于 Step 2 "翻译为本地语" 选项) */
  localLang: LanguageCode;
  /** 本国主语言显示名(本地语写法) */
  localLangName: string;
  regNo: {
    /** 凭证名(显示在 Step 3 字段 label),如 "SSM 注册号" */
    label: string;
    /** 凭证规则提示,如 "12 位纯数字" */
    hint: string;
    /** 占位正则(TODO(REG-RULE) 精确规则待补) */
    regex: RegExp;
    /** 输入规整函数(如 CN 自动转大写+截 18 位、纯数字国家剔除非数字) */
    transform?: (v: string) => string;
  };
}

export const COUNTRIES = [
  {
    code: "CN",
    nameZh: "中国",
    nameEn: "China",
    localLang: "zh",
    localLangName: "中文",
    regNo: {
      label: "统一社会信用代码",
      hint: "18 位",
      // TODO(REG-RULE):国标 GB 32100-2015 校验位算法待补,本轮只验长度+字符集
      regex: /^[0-9A-Z]{18}$/,
      transform: (v: string) => v.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 18),
    },
  },
  {
    code: "KH",
    nameZh: "柬埔寨",
    nameEn: "Cambodia",
    localLang: "km",
    localLangName: "ខ្មែរ",
    regNo: {
      label: "MOC 注册号",
      hint: "6-12 位数字",
      regex: /^[0-9]{6,12}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 12),
    },
  },
  {
    code: "PK",
    nameZh: "巴基斯坦",
    nameEn: "Pakistan",
    localLang: "ur",
    localLangName: "اُردُو",
    regNo: {
      label: "NTN 税号",
      hint: "7-8 位数字",
      regex: /^[0-9]{7,8}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 8),
    },
  },
  {
    code: "MA",
    nameZh: "摩洛哥",
    nameEn: "Morocco",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "RC 商业登记号",
      hint: "20 位以内数字",
      regex: /^[0-9]{1,20}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 20),
    },
  },
  {
    code: "IQ",
    nameZh: "伊拉克",
    nameEn: "Iraq",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "商业登记号",
      hint: "30 位以内",
      regex: /^.{1,30}$/,
      transform: (v: string) => v.slice(0, 30),
    },
  },
  {
    code: "ID",
    nameZh: "印尼",
    nameEn: "Indonesia",
    localLang: "id",
    localLangName: "Bahasa Indonesia",
    regNo: {
      label: "NIB(营业识别号)",
      hint: "13 位纯数字",
      regex: /^[0-9]{13}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 13),
    },
  },
  {
    code: "MY",
    nameZh: "马来西亚",
    nameEn: "Malaysia",
    localLang: "ms",
    localLangName: "Bahasa Melayu",
    regNo: {
      label: "SSM 注册号",
      hint: "12 位纯数字",
      regex: /^[0-9]{12}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 12),
    },
  },
  {
    code: "SA",
    nameZh: "沙特阿拉伯",
    nameEn: "Saudi Arabia",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "CR 商业登记号",
      hint: "10 位数字",
      regex: /^[0-9]{10}$/,
      transform: (v: string) => v.replace(/\D/g, "").slice(0, 10),
    },
  },
  {
    code: "AE",
    nameZh: "阿联酋",
    nameEn: "UAE",
    localLang: "ar",
    localLangName: "العربية",
    regNo: {
      label: "营业执照号(Trade License No)",
      hint: "30 位以内",
      regex: /^.{1,30}$/,
      transform: (v: string) => v.slice(0, 30),
    },
  },
] as const satisfies readonly CountryRule[];

export type CountryCode =
  | "CN" | "KH" | "PK" | "MA" | "IQ" | "ID" | "MY" | "SA" | "AE";

/** language_preference 合法值并集(zh + en + 9 国 localLang 去重)。与后端 LANGUAGE_CODES 必须一致 */
export const LANGUAGE_CODES = ["zh", "en", "km", "ur", "ar", "id", "ms"] as const;
export type LanguageCode = typeof LANGUAGE_CODES[number];

/** 重复注册错误文案:前后端逐字一致(后端 constants 中同名常量),不暴露任何 owner 信息 */
export const DUPLICATE_REGISTRATION_ERROR_MESSAGE =
  "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。";

/** SupplierOrg 状态字符串(未来增 status 时统一加在此处) */
export const STATUS_DRAFT = "DRAFT";

/** sessionStorage 草稿 key(PRD v1.3 §2.3) */
export const DRAFT_STORAGE_KEY = "register_supplier_draft";

/** Step 1 选中国家后的浅蓝信息条文案(数据驱动) */
export function countryHintTemplate(c: CountryRule): string {
  return `您选择了 ${c.nameZh}。后续系统将要求您提供 ${c.regNo.label}(${c.regNo.hint})作为核心准入凭证。`;
}

/** O(1) 查表:code → 配置 */
export function getCountryByCode(code: string): CountryRule | undefined {
  return COUNTRIES.find((c) => c.code === code);
}
