"use client";

import React from "react";
import { SessionProvider } from "next-auth/react";
import { WorkspaceProvider } from "@/context/WorkspaceContext";
import { AuthGate } from "@/components/AuthGate";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AuthGate>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </AuthGate>
    </SessionProvider>
  );
}
