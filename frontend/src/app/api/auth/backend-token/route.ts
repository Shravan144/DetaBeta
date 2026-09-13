import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import { auth } from "@/auth";

export async function GET() {
  const session = await auth();

  if (!session?.user) {
    return NextResponse.json(
      { error: "Not authenticated" },
      { status: 401 },
    );
  }

  const subject = session.user.id ?? session.user.email;
  if (!subject) {
    return NextResponse.json(
      { error: "Authenticated session has no stable user identifier." },
      { status: 401 },
    );
  }

  const secret = process.env.BACKEND_JWT_SECRET ?? "";
  if (secret.length < 32) {
    return NextResponse.json(
      { error: "BACKEND_JWT_SECRET is not configured or too short." },
      { status: 503 },
    );
  }

  const encoder = new TextEncoder();
  const now = Math.floor(Date.now() / 1000);

  const token = await new SignJWT({
    sub: subject,
    email: session.user.email ?? undefined,
    name: session.user.name ?? undefined,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(now + 600) // 10 minutes
    .setIssuer("detabeta-frontend")
    .setAudience("detabeta-api")
    .sign(encoder.encode(secret));

  return NextResponse.json(
    { token },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
