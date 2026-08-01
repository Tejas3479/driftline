"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { User } from "@/app/api";

interface AuthContextType {
  user: User | null;
  login: (user: User) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Fetch user profile to verify session via httpOnly cookie
    fetch("/api/v1/auth/me", {
      credentials: "include",
    })
      .then((res) => {
        if (res.ok) {
          return res.json();
        }
        throw new Error("Invalid session");
      })
      .then((userData) => {
        setUser(userData);
      })
      .catch(() => {
        // Session invalid
        setUser(null);
        if (pathname.startsWith("/dashboard") || pathname.startsWith("/settings") || pathname.startsWith("/anomalies") || pathname.startsWith("/metrics")) {
          router.push("/login");
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [pathname, router]);

  const login = (newUser: User) => {
    setUser(newUser);
    router.push("/dashboard");
  };

  const logout = async () => {
    try {
      await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {
      console.error("Logout error", e);
    }
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
