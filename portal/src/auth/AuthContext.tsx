import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearIdentity,
  loadIdentity,
  saveIdentity,
  type Identity,
} from "./session";

type AuthContextValue = {
  identity: Identity | null;
  signIn: (identity: Identity) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(() => loadIdentity());

  const signIn = useCallback((next: Identity) => {
    saveIdentity(next);
    setIdentity(next);
  }, []);

  const signOut = useCallback(() => {
    clearIdentity();
    setIdentity(null);
  }, []);

  const value = useMemo(
    () => ({ identity, signIn, signOut }),
    [identity, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
