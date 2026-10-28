import { getJson } from '../management-api';

export type Organization = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  primary_organizer: string | null;
  invitation_delivery_status: string | null;
};
export type OrganizationPage = {
  organizations: Organization[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export function organizationPage(query: string, offset = 0, limit = 25) {
  const params = new URLSearchParams({ q: query, offset: String(offset), limit: String(limit) });
  return getJson<OrganizationPage>(`/api/v1/platform/organizations?${params}`);
}

export function organizationDetail(id: string) {
  return getJson<Organization>(`/api/v1/platform/organizations/${encodeURIComponent(id)}`);
}
