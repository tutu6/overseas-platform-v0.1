"use client";

// 3 步向导顶部步骤条。配色:已选/当前 深蓝 #003366,未到 灰。

interface StepIndicatorProps {
  current: 1 | 2 | 3;
}

const STEPS: { num: 1 | 2 | 3; label: string }[] = [
  { num: 1, label: "选择属地" },
  { num: 2, label: "语言偏好" },
  { num: 3, label: "注册填报" },
];

export function StepIndicator({ current }: StepIndicatorProps) {
  return (
    <div className="mb-6 flex items-center justify-between">
      {STEPS.map((s, idx) => {
        const done = current > s.num;
        const active = current === s.num;
        return (
          <div key={s.num} className="flex flex-1 items-center">
            <div className="flex flex-col items-center">
              <div
                className={
                  "flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-colors " +
                  (done || active
                    ? "bg-[#003366] text-white"
                    : "bg-gray-200 text-gray-500")
                }
              >
                {s.num}
              </div>
              <span
                className={
                  "mt-1.5 text-xs " +
                  (done || active ? "font-semibold text-[#003366]" : "text-gray-400")
                }
              >
                {s.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={
                  "mx-2 h-0.5 flex-1 " + (done ? "bg-[#003366]" : "bg-gray-200")
                }
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
