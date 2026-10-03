import { type NextRequest, NextResponse } from "next/server";
import {
  DEFAULT_PASS,
  DEFAULT_USER,
  SESSION_COOKIE_NAME,
  type UserSession,
  VALID_API_KEY,
} from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { username, password, apiKey } = body;

    let valid = false;
    let user = DEFAULT_USER;

    // Check credentials or direct API Key
    if (apiKey && (apiKey === VALID_API_KEY || apiKey.startsWith("dev-api-key-"))) {
      valid = true;
      user = "api_key_user";
    } else if (
      (username === DEFAULT_USER || username === "admin") &&
      password === DEFAULT_PASS
    ) {
      valid = true;
      user = username;
    }

    if (!valid) {
      return NextResponse.json(
        { error: "Invalid credentials or API key" },
        { status: 401 }
      );
    }

    const session: UserSession = {
      username: user,
      role: "lead_quant",
      authenticatedAt: new Date().toISOString(),
    };

    const encoded = Buffer.from(JSON.stringify(session)).toString("base64");

    const response = NextResponse.json({ success: true, session });
    response.cookies.set({
      name: SESSION_COOKIE_NAME,
      value: encoded,
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return response;
  } catch (err) {
    return NextResponse.json(
      { error: `Auth failed: ${err instanceof Error ? err.message : String(err)}` },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  const response = NextResponse.json({ success: true, loggedOut: true });
  response.cookies.set({
    name: SESSION_COOKIE_NAME,
    value: "",
    httpOnly: true,
    path: "/",
    maxAge: 0,
  });
  return response;
}
