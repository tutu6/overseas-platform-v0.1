import { create } from "zustand";
import type { MeData, RoleCode } from "@/lib/auth";

interface AuthState {
  user: MeData | null;
  loaded: boolean;
  setUser: (u: MeData | null) => void;
  setLoaded: (b: boolean) => void;
  reset: () => void;
  hasPermission: (code: string) => boolean;
  hasRole: (code: RoleCode) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loaded: false,
  setUser: (u) => set({ user: u }),
  setLoaded: (b) => set({ loaded: b }),
  reset: () => set({ user: null, loaded: true }),
  hasPermission: (code) => {
    const u = get().user;
    return !!u && u.permissions.includes(code);
  },
  hasRole: (code) => {
    const u = get().user;
    return !!u && u.roles.includes(code);
  },
}));
