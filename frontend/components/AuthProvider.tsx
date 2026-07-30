"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { User } from "@/app/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Check localStorage on mount
    const storedToken = localStorage.getItem("driftline_token");
    if (storedToken) {
      setToken(storedToken);
      // Fetch user profile to verify token
      fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${storedToken}` },
      })
        .then((res) => {
          if (res.ok) {
            return res.json();
          }
          throw new Error("Invalid token");
        })
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          // Token invalid
          localStorage.removeItem("driftline_token");
          setToken(null);
          setUser(null);
          if (pathname.startsWith("/dashboard") || pathname.startsWith("/settings") || pathname.startsWith("/anomalies") || pathname.startsWith("/metrics")) {
            router.push("/login");
          }
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
      if (pathname.startsWith("/dashboard") || pathname.startsWith("/settings") || pathname.startsWith("/anomalies") || pathname.startsWith("/metrics")) {
        router.push("/login");
      }
    }
  }, [pathname, router]);

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem("driftline_token", newToken);
    setToken(newToken);
    setUser(newUser);
    router.push("/dashboard");
  };

  const logout = () => {
    localStorage.removeItem("driftline_token");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
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
