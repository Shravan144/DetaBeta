"use client";

import React, { useEffect, useState } from "react";
import { getProviders, useSession, signIn } from "next-auth/react";
import { Loader2, Mail, AlertTriangle } from "lucide-react";

/**
 * Wraps the application and shows a sign-in screen for unauthenticated users.
 * If no OAuth providers are configured, shows a configuration warning.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useSession();

  if (status === "loading") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
          <p className="text-sm text-zinc-400">Loading session…</p>
        </div>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <SignInScreen />;
  }

  return <>{children}</>;
}

function SignInScreen() {
  const [providers, setProviders] = useState<Awaited<ReturnType<typeof getProviders>>>(null);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getProviders()
      .then((availableProviders) => {
        if (!cancelled) setProviders(availableProviders);
      })
      .finally(() => {
        if (!cancelled) setProvidersLoaded(true);
      });
    return () => { cancelled = true; };
  }, []);

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      if (result?.error) {
        setError("Invalid email or password.");
      }
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-zinc-950">
      <div className="w-full max-w-sm space-y-6 rounded-xl border border-zinc-800 bg-zinc-900/50 p-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500 text-lg font-black text-zinc-950">
            Δ
          </div>
          <h1 className="text-lg font-bold tracking-wide text-zinc-100">
            DETABETA
          </h1>
          <p className="text-xs text-zinc-500">
            Sign in to your data science laboratory
          </p>
        </div>

        {/* OAuth buttons */}
        {(providers?.github || providers?.google) && (
          <div className="space-y-2">
          {providers?.github && (
          <button
            onClick={() => signIn("github")}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-zinc-700 cursor-pointer"
          >
            <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            Continue with GitHub
          </button>
          )}
          {providers?.google && (
          <button
            onClick={() => signIn("google")}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-zinc-700 cursor-pointer"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Continue with Google
          </button>
          )}
          </div>
        )}

        {/* Divider */}
        {providers?.credentials && (providers?.github || providers?.google) && (
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-zinc-800" />
            <span className="text-[10px] uppercase tracking-widest text-zinc-600">
              or
            </span>
            <div className="h-px flex-1 bg-zinc-800" />
          </div>
        )}

        {/* Credentials form */}
        {providers?.credentials && (
        <form onSubmit={handleCredentialsSubmit} className="space-y-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
          {error && (
            <p className="flex items-center gap-1 text-xs text-rose-400">
              <AlertTriangle className="h-3 w-3" />
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-600 disabled:opacity-50 cursor-pointer"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mail className="h-4 w-4" />
            )}
            Sign in with Email
          </button>
        </form>
        )}

        {providersLoaded && !providers?.github && !providers?.google && !providers?.credentials && (
          <p className="flex items-start gap-2 rounded-lg border border-amber-900/40 bg-amber-950/20 p-3 text-xs text-amber-300">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            No sign-in provider is configured. Add Google, GitHub, or secure demo credentials on the server.
          </p>
        )}

        <p className="text-center text-[10px] text-zinc-600">
          Authentication powered by NextAuth.js
        </p>
      </div>
    </div>
  );
}
