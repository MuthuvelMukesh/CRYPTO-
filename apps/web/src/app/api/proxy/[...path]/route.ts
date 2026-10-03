import { type NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.INTERNAL_API_KEY || "dev-api-key-researcher-1";

async function proxyRequest(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const path = resolvedParams.path ? resolvedParams.path.join("/") : "";
  const search = request.nextUrl.search;
  const targetUrl = `${BACKEND_URL}/${path}${search}`;

  const headers = new Headers();
  headers.set("X-API-Key", API_KEY);
  headers.set("Accept", "application/json");

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  const idempotencyKey = request.headers.get("Idempotency-Key");
  if (idempotencyKey) {
    headers.set("Idempotency-Key", idempotencyKey);
  }

  let body: BodyInit | null = null;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.text();
  }

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });

    const responseData = await response.text();
    const returnHeaders = new Headers();
    returnHeaders.set("Content-Type", response.headers.get("content-type") || "application/json");

    return new NextResponse(responseData, {
      status: response.status,
      headers: returnHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      {
        type: "https://httpstatuses.com/502",
        title: "Bad Gateway",
        status: 502,
        detail: `Failed to communicate with quant API backend: ${error instanceof Error ? error.message : String(error)}`,
      },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
