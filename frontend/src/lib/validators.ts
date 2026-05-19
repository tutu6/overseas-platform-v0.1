// 集中前端字段校验规则。后端规则在 schemas/auth.py 与 schemas/me.py。
// 返回 null = 通过;返回字符串 = 错误文案。

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PHONE_RE = /^1[3-9]\d{9}$/;
// 与后端 USERNAME_REGEX 等价:3-50 位字母/数字/下划线/短横,不能纯数字
export const USERNAME_RE = /^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$/;
// 18 位大写字母 + 数字(国标 GB 32100-2015)
export const USC_RE = /^[0-9A-Z]{18}$/;
// 与后端 validate_password_strength 等价:8-32 位,至少 1 字母 + 1 数字
export const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&^_\-]{8,32}$/;

export function validateEmail(v: string): string | null {
  if (!v) return "请填写邮箱";
  if (!EMAIL_RE.test(v)) return "邮箱格式不正确";
  return null;
}

/** 选填手机号:留空通过;若提供则校验格式。 */
export function validatePhoneOptional(v: string): string | null {
  if (!v) return null;
  if (!PHONE_RE.test(v)) return "手机号须为 11 位中国大陆号码(1 开头,第二位 3-9)";
  return null;
}

/** 必填手机号。 */
export function validatePhoneRequired(v: string): string | null {
  if (!v) return "请填写手机号";
  return validatePhoneOptional(v);
}

/** 选填用户名:留空通过;若提供则校验格式。 */
export function validateUsernameOptional(v: string): string | null {
  if (!v) return null;
  if (!USERNAME_RE.test(v))
    return "用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字";
  return null;
}

export function validateUsc(v: string): string | null {
  if (!v) return "请填写统一社会信用代码";
  if (!USC_RE.test(v)) return "统一社会信用代码须为 18 位大写字母与数字";
  return null;
}

export function validatePassword(v: string): string | null {
  if (!v) return "请填写密码";
  if (!PASSWORD_RE.test(v)) return "密码 8-32 位,至少包含 1 个字母与 1 个数字";
  return null;
}

export function validatePasswordConfirm(pwd: string, confirm: string): string | null {
  if (!confirm) return "请再次输入密码";
  if (pwd !== confirm) return "两次密码不一致";
  return null;
}

export function validateRequired(v: string, label = "此项"): string | null {
  if (!v.trim()) return `${label}不能为空`;
  return null;
}
