import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  AuthContextType,
  LoginPayload,
  OrganizationMembershipDetail,
  RegisterPayload,
  User,
} from '../types/auth';
import { apiClient, setOnUnauthorizedHandler } from '../services/api';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<OrganizationMembershipDetail[]>([]);
  const [activeOrg, setActiveOrg] = useState<OrganizationMembershipDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const resolveActiveOrg = useCallback(
    (members: OrganizationMembershipDetail[], preferredOrgId?: string | null) => {
      if (members.length === 0) return null;
      if (preferredOrgId) {
        const found = members.find((m) => m.organization_id === preferredOrgId);
        if (found) return found;
      }
      const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('docufin_active_org_id') : null;
      if (stored) {
        const found = members.find((m) => m.organization_id === stored);
        if (found) return found;
      }
      return members[0];
    },
    []
  );

  const refreshUser = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await apiClient.getMe();
      setUser(data.user);
      setMemberships(data.memberships);

      const active = resolveActiveOrg(data.memberships, data.active_organization_id);
      setActiveOrg(active);
      if (active && typeof localStorage !== 'undefined') {
        localStorage.setItem('docufin_active_org_id', active.organization_id);
      }
    } catch {
      setUser(null);
      setMemberships([]);
      setActiveOrg(null);
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('docufin_active_org_id');
      }
    } finally {
      setIsLoading(false);
    }
  }, [resolveActiveOrg]);

  useEffect(() => {
    setOnUnauthorizedHandler(() => {
      setUser(null);
      setMemberships([]);
      setActiveOrg(null);
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('docufin_active_org_id');
      }
    });

    refreshUser();
  }, [refreshUser]);

  const login = async (payload: LoginPayload) => {
    await apiClient.login(payload);
    await refreshUser();
  };

  const register = async (payload: RegisterPayload) => {
    await apiClient.register(payload);
    await refreshUser();
  };

  const logout = async () => {
    try {
      await apiClient.logout();
    } finally {
      setUser(null);
      setMemberships([]);
      setActiveOrg(null);
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('docufin_active_org_id');
      }
    }
  };

  const switchOrganization = (orgId: string) => {
    const selected = memberships.find((m) => m.organization_id === orgId);
    if (selected) {
      setActiveOrg(selected);
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('docufin_active_org_id', selected.organization_id);
      }
    }
  };

  const value: AuthContextType = {
    user,
    memberships,
    activeOrg,
    activeRole: activeOrg?.role || null,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    switchOrganization,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
