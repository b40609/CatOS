import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

// Frontend-only mock auth: accounts live in localStorage. NOT real security.
export type MockUser = {
  email: string;
  name: string;
  avatar: string; // emoji or short glyph
  provider: "email" | "google";
  joinedAt: string;
};

type Account = MockUser & { password?: string };

const USERS_KEY = "catos.mock.accounts";
const SESSION_KEY = "catos.mock.session";
const OUT_KEY = "catos.mock.signedout";

type AuthCtx = {
  user: MockUser | null;
  ready: boolean;
  signUp: (name: string, email: string, password: string) => string | null;
  signIn: (email: string, password: string) => string | null;
  signInGoogle: () => void;
  updateProfile: (p: Partial<Pick<MockUser, "name" | "avatar">>) => void;
  signOut: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

function loadAccounts(): Record<string, Account> {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY) ?? "{}");
  } catch {
    return {};
  }
}
function saveAccounts(a: Record<string, Account>) {
  localStorage.setItem(USERS_KEY, JSON.stringify(a));
}
function strip({ password: _p, ...u }: Account): MockUser {
  return u;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MockUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const email = localStorage.getItem(SESSION_KEY);
    const acc = email ? loadAccounts()[email] : undefined;
    if (acc) setUser(strip(acc));
    else if (!localStorage.getItem(OUT_KEY)) signInGoogle();
    setReady(true);
  }, []);

  const start = useCallback((acc: Account) => {
    localStorage.setItem(SESSION_KEY, acc.email);
    localStorage.removeItem(OUT_KEY);
    setUser(strip(acc));
  }, []);

  const signUp: AuthCtx["signUp"] = (name, email, password) => {
    const key = email.trim().toLowerCase();
    const accs = loadAccounts();
    if (accs[key]) return "此 Email 已註冊";
    const acc: Account = {
      email: key,
      name: name.trim() || (key.split("@")[0] ?? key),
      avatar: "^ω^",
      provider: "email",
      joinedAt: new Date().toISOString(),
      password,
    };
    accs[key] = acc;
    saveAccounts(accs);
    start(acc);
    return null;
  };

  const signIn: AuthCtx["signIn"] = (email, password) => {
    const acc = loadAccounts()[email.trim().toLowerCase()];
    if (!acc || acc.password !== password) return "Email 或密碼錯誤";
    start(acc);
    return null;
  };

  const signInGoogle = () => {
    const key = "trader@gmail.com";
    const accs = loadAccounts();
    const acc: Account = accs[key] ?? {
      email: key,
      name: "Min Yi",
      avatar: "₿",
      provider: "google",
      joinedAt: new Date().toISOString(),
    };
    accs[key] = acc;
    saveAccounts(accs);
    start(acc);
  };

  const updateProfile: AuthCtx["updateProfile"] = (p) => {
    if (!user) return;
    const accs = loadAccounts();
    const prev = accs[user.email] ?? user;
    const acc: Account = { ...prev, ...(p.name ? { name: p.name } : {}), ...(p.avatar ? { avatar: p.avatar } : {}) };
    accs[user.email] = acc;
    saveAccounts(accs);
    setUser(strip(acc));
  };

  const signOut = () => {
    localStorage.removeItem(SESSION_KEY);
    localStorage.setItem(OUT_KEY, "1");
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, ready, signUp, signIn, signInGoogle, updateProfile, signOut }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
