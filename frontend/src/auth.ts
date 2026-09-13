import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";

const authSecret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET;
const demoEmail = process.env.DEMO_USER_EMAIL?.trim();
const demoPassword = process.env.DEMO_USER_PASSWORD;
const demoLoginEnabled = Boolean(
  demoEmail && demoPassword && demoPassword.length >= 12,
);

export const { handlers, auth, signIn, signOut } = NextAuth({
  // Auth.js must fail closed when the deployment has no configured secret.
  // Never substitute a source-controlled development secret here.
  secret: authSecret,
  providers: [
    // GitHub OAuth — enabled when GITHUB_ID + GITHUB_SECRET are set.
    ...(process.env.GITHUB_ID && process.env.GITHUB_SECRET
      ? [
          GitHub({
            clientId: process.env.GITHUB_ID,
            clientSecret: process.env.GITHUB_SECRET,
          }),
        ]
      : []),

    // Google OAuth — enabled when GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET are set.
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
      ? [
          Google({
            clientId: process.env.GOOGLE_CLIENT_ID,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET,
          }),
        ]
      : []),

    // Optional demo login. Both values must be explicitly configured and the
    // password must be at least 12 characters; otherwise the provider is absent.
    ...(demoLoginEnabled
      ? [
          Credentials({
            name: "Email",
            credentials: {
              email: { label: "Email", type: "email" },
              password: { label: "Password", type: "password" },
            },
            async authorize(credentials) {
              const email = credentials?.email as string | undefined;
              const password = credentials?.password as string | undefined;
              if (
                email === demoEmail &&
                password === demoPassword
              ) {
                return {
                  id: `credentials:${email}`,
                  email,
                  name: process.env.DEMO_USER_NAME || "Demo User",
                };
              }
              return null;
            },
          }),
        ]
      : []),
  ],

  session: { strategy: "jwt" },

  callbacks: {
    async jwt({ token, user, account }) {
      // On initial sign-in, persist the provider-scoped user ID.
      if (user && account) {
        token.userId = account.provider === "credentials"
          ? user.id
          : `${account.provider}:${account.providerAccountId}`;
      }
      return token;
    },
    async session({ session, token }) {
      // Expose the provider user ID as session.user.id.
      if (session.user && token.userId) {
        session.user.id = token.userId as string;
      }
      return session;
    },
  },

  pages: {
    signIn: "/",  // We handle sign-in UI ourselves via AuthGate.
    error: "/",   // Redirect auth errors to the root landing/login page.
  },
});
