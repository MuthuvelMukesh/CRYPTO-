import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "crypto_quant_session";
export const DEFAULT_USER = "researcher";
export const DEFAULT_PASS = process.env.DASHBOARD_PASSWORD || "quant-v3-secret";
export const VALID_API_KEY = process.env.INTERNAL_API_KEY || "dev-api-key-researcher-1";

export interface UserSession {
  username: string;
  role: "lead_quant" | "researcher" | "read_only";
  authenticatedAt: string;
}

/**
 * Validate session from cookie store (Server-side).
 */
export async function getServerSession(): Promise<UserSession | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME);

  if (!sessionCookie || !sessionCookie.value) {
    return null;
  }

  try {
    const parsed = JSON.parse(
      Buffer.from(sessionCookie.value, "base64").toString("utf-8")
    ) as UserSession;

    if (parsed && parsed.username) {
      return parsed;
    }
  } catch {
    return null;
  }

  return null;
}
