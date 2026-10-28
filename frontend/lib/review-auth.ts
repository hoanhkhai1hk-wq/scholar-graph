export const REVIEW_COOKIE = "sg_review_session";
export async function signature(value: string, secret: string) {
  const bytes = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", bytes.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signed = new Uint8Array(await crypto.subtle.sign("HMAC", key, bytes.encode(value)));
  return Array.from(signed, byte => byte.toString(16).padStart(2, "0")).join("");
}
export function equal(a: string, b: string) { let diff = a.length ^ b.length; for (let i = 0; i < Math.max(a.length, b.length); i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0); return diff === 0; }
export async function validSession(value: string, secret: string) {
  const [expires, nonce, signed, extra] = value.split(".");
  if (extra || !/^\d{13}$/.test(expires ?? "") || !/^[a-f0-9]{32}$/.test(nonce ?? "") || !/^[a-f0-9]{64}$/.test(signed ?? "") || Number(expires) <= Date.now() || Number(expires) > Date.now() + 25 * 3600 * 1000) return false;
  return equal(signed, await signature(`${expires}.${nonce}`, secret));
}
