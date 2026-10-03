import createClient from "openapi-fetch";
import type { paths } from "./schema";

/**
 * Base URL determination:
 * On client (browser): Requests go through Next.js BFF proxy `/api/proxy` to hide keys and prevent CORS.
 * On server (SSR/RSC): Requests go directly to FastAPI backend `http://127.0.0.1:8000`.
 */
const isServer = typeof window === "undefined";
const API_BASE_URL = isServer
  ? process.env.INTERNAL_API_URL || "http://127.0.0.1:8000"
  : "/api/proxy";

export const apiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: isServer
    ? {
        "X-API-Key": process.env.INTERNAL_API_KEY || "dev-api-key-researcher-1",
        "Content-Type": "application/json",
      }
    : {
        "Content-Type": "application/json",
      },
});

export type ApiPaths = paths;
