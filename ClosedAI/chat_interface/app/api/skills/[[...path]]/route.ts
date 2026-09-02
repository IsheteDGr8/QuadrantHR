import { NextRequest } from "next/server"
import { proxyToBackend } from "@/lib/backend-proxy"

/* Proxy for /api/skills and /api/skills/* -> backend /api/skills/*
 * Uses optional catch-all so POST /api/skills (no extra segment) resolves.
 * Required catch-all [...path] returned 404 for the catalog load request. */

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "skills")
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "skills")
}

export async function PATCH(request: NextRequest) {
  return proxyToBackend(request, "skills")
}

export async function DELETE(request: NextRequest) {
  return proxyToBackend(request, "skills")
}
