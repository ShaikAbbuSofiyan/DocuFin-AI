export type Role = 'Admin' | 'Analyst' | 'Reviewer';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface OrganizationMembershipDetail {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: Role;
  is_active: boolean;
}

export interface UserMeResponse {
  user: User;
  memberships: OrganizationMembershipDetail[];
  active_organization_id: string | null;
  active_role: Role | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  organization_name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AuthContextType {
  user: User | null;
  memberships: OrganizationMembershipDetail[];
  activeOrg: OrganizationMembershipDetail | null;
  activeRole: Role | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  switchOrganization: (orgId: string) => void;
  refreshUser: () => Promise<void>;
}
