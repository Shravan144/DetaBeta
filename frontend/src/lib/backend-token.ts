/**
 * Client-side backend token manager.
 *
 * Caches the JWT obtained from /api/auth/backend-token in memory until
 * shortly before it expires, then transparently fetches a new one.
 */

let cachedToken: string | null = null;
let tokenExpiresAt = 0; // Unix ms

/** Clear the cached backend token (call on sign-out or 401). */
export function clearBackendToken(): void {
  cachedToken = null;
  tokenExpiresAt = 0;
}

/**
 * Return a valid backend JWT, fetching a fresh one if the cache is empty
 * or the current token expires within 2 minutes.
 */
export async function getBackendToken(): Promise<string> {
  const bufferMs = 2 * 60 * 1000; // refresh 2 min before expiry
  if (cachedToken && Date.now() < tokenExpiresAt - bufferMs) {
    return cachedToken;
  }

  const res = await fetch("/api/auth/backend-token");
  if (!res.ok) {
    clearBackendToken();
    const detail = await res.text();
    throw new Error(`Failed to obtain backend token: ${res.status} ${detail}`);
  }

  const { token } = (await res.json()) as { token: string };

  // Decode the JWT payload (base64url) to read exp.
  try {
    const payloadB64 = token.split(".")[1];
    const payload = JSON.parse(atob(payloadB64)) as { exp?: number };
    tokenExpiresAt = (payload.exp ?? 0) * 1000;
  } catch {
    // If decoding fails, assume 8 min lifetime.
    tokenExpiresAt = Date.now() + 8 * 60 * 1000;
  }

  cachedToken = token;
  return token;
}
