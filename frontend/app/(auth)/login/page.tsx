"use client";

import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";
import GlowButton from "@/components/GlowButton";
import { AlertCircle, LogIn, Lock, Mail } from "lucide-react";
import PageTransition from "@/components/PageTransition";
import AtroposCard from "@/components/AtroposCard";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Invalid credentials");
      }

      const data = await response.json();
      
      // Fetch user profile
      const userResponse = await fetch("/api/v1/auth/me", {
        credentials: "include"
      });
      const userData = await userResponse.json();
      
      login(userData);
    } catch (err) {
      setError("Invalid email or password. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PageTransition>
      <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-slate-950 p-4">
        {/* Background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/10 blur-[120px] rounded-full pointer-events-none" />
        
        <div className="w-full max-w-md z-10">
          <AtroposCard className="w-full">
            <div className="p-8 backdrop-blur-xl bg-slate-900/60 border border-slate-800 rounded-3xl">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-cyan-500/20 text-cyan-400 mb-4 border border-cyan-500/30">
                  <LogIn className="w-6 h-6" />
                </div>
                <h1 className="text-2xl font-bold text-white mb-2">Welcome Back</h1>
                <p className="text-slate-400 text-sm">Sign in to your Driftline dashboard</p>
              </div>

              {error && (
                <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center gap-2 text-sm">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <p>{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="h-4 w-4 text-slate-500" />
                    </div>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      className="block w-full pl-10 pr-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all sm:text-sm"
                      placeholder="you@company.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-4 w-4 text-slate-500" />
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="block w-full pl-10 pr-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all sm:text-sm"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <div className="pt-2">
                  <GlowButton type="submit" disabled={isLoading} className="w-full justify-center">
                    {isLoading ? "Signing in..." : "Sign In"}
                  </GlowButton>
                </div>
              </form>

              <div className="mt-6 text-center text-sm text-slate-400">
                Don't have an account?{" "}
                <Link href="/register" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
                  Create one
                </Link>
              </div>
            </div>
          </AtroposCard>
        </div>
      </div>
    </PageTransition>
  );
}
