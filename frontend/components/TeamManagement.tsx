"use client";

import React, { useEffect, useState } from "react";
import { User, fetchTeamMembers, addTeamMember, removeTeamMember, updateTeamMemberRole } from "@/app/api";
import { useAuth } from "@/components/AuthProvider";
import { Users, Shield, Trash2, Plus, AlertTriangle, Activity, UserPlus } from "lucide-react";
import ScrollReveal from "./ScrollReveal";

export default function TeamManagement() {
  const { user: currentUser } = useAuth();
  const [members, setMembers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add User Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("member");
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const loadMembers = async () => {
    if (!currentUser) return;
    try {
      setLoading(true);
      const data = await fetchTeamMembers(currentUser.workspace_id);
      setMembers(data);
    } catch (err: any) {
      setError(err.message || "Failed to load team members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMembers();
  }, [currentUser]);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser) return;
    try {
      setAddLoading(true);
      setAddError(null);
      await addTeamMember(currentUser.workspace_id, {
        email: newEmail,
        password: newPassword,
        role: newRole,
      });
      await loadMembers();
      setIsAddModalOpen(false);
      setNewEmail("");
      setNewPassword("");
      setNewRole("member");
    } catch (err: any) {
      setAddError(err.message || "Failed to add member");
    } finally {
      setAddLoading(false);
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await updateTeamMemberRole(userId, { role });
      await loadMembers();
    } catch (err: any) {
      alert(err.message || "Failed to update role");
    }
  };

  const handleRemoveMember = async (userId: number) => {
    const confirmDelete = window.confirm("Are you sure you want to remove this user from the workspace?");
    if (!confirmDelete) return;
    try {
      await removeTeamMember(userId);
      await loadMembers();
    } catch (err: any) {
      alert(err.message || "Failed to remove user");
    }
  };

  if (!currentUser) return null;
  const isAdmin = currentUser.role === "admin";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="h-5 w-5 text-cyan-400" /> Workspace Team
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Manage members and administrative roles for Workspace #{currentUser.workspace_id}
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-4 rounded-xl transition-all shadow-lg hover:shadow-glow-cyan-sm"
          >
            <Plus className="h-4 w-4" /> Add Teammate
          </button>
        )}
      </div>

      {!isAdmin && (
        <div className="rounded-xl border border-amber-900 bg-amber-950/20 p-4 text-amber-300 text-sm flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          You are viewing this workspace as a standard member. Administrative actions are disabled.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-900 bg-red-950/20 p-4 text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex h-32 items-center justify-center rounded-xl bg-slate-900 border border-slate-800">
          <Activity className="h-8 w-8 animate-spin text-cyan-400" />
        </div>
      ) : (
        <ScrollReveal>
          <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-950/50 text-xs font-bold uppercase text-slate-500 border-b border-slate-800">
                  <tr>
                    <th className="px-6 py-4">User</th>
                    <th className="px-6 py-4">Role</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {members.map((member) => (
                    <tr key={member.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-bold text-white flex items-center gap-2">
                          {member.email}
                          {member.id === currentUser.id && (
                            <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700">You</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {isAdmin && member.id !== currentUser.id ? (
                          <select
                            value={member.role}
                            onChange={(e) => handleRoleChange(member.id, e.target.value)}
                            className="bg-slate-950 border border-slate-700 text-xs font-bold rounded-lg px-2 py-1 focus:outline-none focus:border-cyan-500 text-slate-300 uppercase"
                          >
                            <option value="member">Member</option>
                            <option value="admin">Admin</option>
                          </select>
                        ) : (
                          <span className={`inline-flex items-center gap-1 text-xs font-bold uppercase px-2 py-1 rounded-lg ${member.role === 'admin' ? 'bg-purple-950/50 text-purple-400 border border-purple-900/50' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
                            {member.role === 'admin' && <Shield className="h-3 w-3" />}
                            {member.role}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {isAdmin && member.id !== currentUser.id && (
                          <button
                            onClick={() => handleRemoveMember(member.id)}
                            className="text-slate-500 hover:text-red-400 transition-colors p-1"
                            title="Remove User"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </ScrollReveal>
      )}

      {/* Add User Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-cyan-400" />
                Add New Teammate
              </h3>
              <button 
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            {addError && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {addError}
              </div>
            )}

            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Email</label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  placeholder="colleague@acme.com"
                />
              </div>
              
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Initial Password</label>
                <input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  placeholder="Secure string to share out-of-band"
                />
                <p className="text-[10px] text-slate-500 mt-1">Share this password with the user. They can change it later.</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500 uppercase text-sm"
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div className="pt-4 flex gap-3">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl border border-slate-700 font-bold text-slate-300 hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addLoading}
                  className="flex-1 py-2.5 rounded-xl bg-cyan-600 font-bold text-white hover:bg-cyan-500 transition-colors disabled:opacity-50 flex items-center justify-center"
                >
                  {addLoading ? <Activity className="h-4 w-4 animate-spin" /> : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
