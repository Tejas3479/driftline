"use client";

import React, { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";
import GlowButton from "@/components/GlowButton";
import { AlertCircle, UserPlus, Lock, Mail, Building } from "lucide-react";
import PageTransition from "@/components/PageTransition";
import AtroposCard from "@/components/AtroposCard";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      // 1. Register
      const regResponse = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          workspace_name: workspaceName,
          role: "member"
        }),
      });

      if (!regResponse.ok) {
        const errorData = await regResponse.json();
        throw new Error(errorData.detail || "Registration failed");
      }

      // 2. Login
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const loginResponse = await fetch("/api/v1/auth/login", {
        method: "POST",
        body: formData,
      });

      if (!loginResponse.ok) {
        throw new Error("Login after registration failed");
      }

      const data = await loginResponse.json();
      
      // 3. Fetch user
      const userResponse = await fetch("/api/v1/auth/me", {
        credentials: "include"
      });
      const userData = await userResponse.json();
      
      login(userData);} catch (e: unknown) {  const err = e instanceof Error ? e : new Error(String(e));
      setError(err.message || "An error occurred. Please try again.");
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
                  <UserPlus className="w-6 h-6" />
                </div>
                <h1 className="text-2xl font-bold text-white mb-2">Create Account</h1>
                <p className="text-slate-400 text-sm">Join Driftline to start monitoring</p>
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
                      className="block w-full pl-10 pr-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-hidden focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all sm:text-sm"
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
                      className="block w-full pl-10 pr-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-hidden focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all sm:text-sm"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Workspace Name</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Building className="h-4 w-4 text-slate-500" />
                    </div>
                    <input
                      type="text"
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                      required
                      className="block w-full pl-10 pr-3 py-2.5 bg-slate-950/50 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-hidden focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all sm:text-sm"
                      placeholder="Acme Corp"
                    />
                  </div>
                </div>

                <div className="pt-2">
                  <GlowButton type="submit" disabled={isLoading} className="w-full justify-center">
                    {isLoading ? "Creating account..." : "Sign Up"}
                  </GlowButton>
                </div>
              </form>

              <div className="mt-6 text-center text-sm text-slate-400">
                Already have an account?{" "}
                <Link href="/login" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
                  Sign in
                </Link>
              </div>
            </div>
          </AtroposCard>
        </div>
      </div>
    </PageTransition>
  );
}
