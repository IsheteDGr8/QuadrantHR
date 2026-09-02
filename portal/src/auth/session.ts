export type Identity = {
  id: string;
  role: string;
  name: string;
};

const STORAGE_KEY = "quadranthr.session";

export function loadIdentity(): Identity | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Identity;
    if (!parsed?.id || !parsed?.role || !parsed?.name) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveIdentity(identity: Identity) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
}

export function clearIdentity() {
  sessionStorage.removeItem(STORAGE_KEY);
}
