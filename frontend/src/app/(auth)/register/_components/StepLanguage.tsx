"use client";

// 3 步向导 Step 2:语言偏好。
// 三个按钮 +「← 返回重选国家」。颜色用项目深蓝/橙(不用截图渐变紫)。
// 本轮只存 language_preference,**不真翻译**(T-I18N)。

import { Globe } from "lucide-react";

import {
  getCountryByCode,
  type CountryCode,
  type LanguageCode,
} from "@/config/country-registration-rules";

interface StepLanguageProps {
  countryCode: CountryCode;
  selected: LanguageCode | "";
  onSelect: (lang: LanguageCode) => void;
  onBack: () => void;
}

export function StepLanguage({ countryCode, selected, onSelect, onBack }: StepLanguageProps) {
  const country = getCountryByCode(countryCode);
  if (!country) return null;

  const options: { lang: LanguageCode; title: string; subtitle: string }[] = [
    {
      lang: country.localLang,
      title: `翻译为 ${country.localLangName}`,
      subtitle: `${country.localLang}-${country.code}`,
    },
    { lang: "en", title: "翻译为 English", subtitle: "en" },
    { lang: "zh", title: "保持中文", subtitle: "zh" },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900">是否开启多语种适配?</h2>
        <p className="mt-1 text-sm text-gray-500">
          检测到您选择了 {country.nameZh}。是否需要启用 Gemini AI 本地化引擎,将后续的注册表单翻译为{" "}
          {country.localLangName} ({country.localLang}-{country.code})?
        </p>
      </div>

      <div className="space-y-3">
        {options.map((opt) => {
          const active = selected === opt.lang;
          return (
            <button
              key={opt.lang + opt.title}
              type="button"
              onClick={() => onSelect(opt.lang)}
              className={
                "flex w-full items-center gap-3 rounded-xl border-2 px-4 py-3 text-left transition-all " +
                (active
                  ? "border-[#FF6B35] bg-[#FF6B35]/5"
                  : "border-gray-200 hover:border-[#003366] hover:bg-[#003366]/5")
              }
            >
              <div
                className={
                  "flex h-10 w-10 items-center justify-center rounded-lg " +
                  (active ? "bg-[#FF6B35]/15" : "bg-gray-50")
                }
              >
                <Globe className={"h-5 w-5 " + (active ? "text-[#FF6B35]" : "text-[#003366]")} />
              </div>
              <div className="flex-1">
                <p
                  className={
                    "text-sm font-semibold " + (active ? "text-[#FF6B35]" : "text-gray-800")
                  }
                >
                  {opt.title}
                </p>
                <p className="text-xs text-gray-400">{opt.subtitle}</p>
              </div>
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={onBack}
        className="text-sm text-gray-500 underline transition-colors hover:text-[#003366]"
      >
        ← 返回重选国家
      </button>
    </div>
  );
}
