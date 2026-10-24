import type { StatusTone } from './ui/Status';

export type DomainState = {
  id: string;
  hostname: string;
  kind: 'custom' | 'fallback';
  ownership: 'pending' | 'checking' | 'verified' | 'failed';
  tls: 'pending' | 'issuing' | 'active' | 'failed';
  routing: 'reserved' | 'ready' | 'active' | 'deactivated';
  primary: boolean;
  serving: boolean;
  error_code: string | null;
};

export type DomainMessage = { title: string; tone: StatusTone; instruction: string };

/** M2-01 vocabulary v1. Presentation components never infer a domain decision. */
export function describeDomain(domain: DomainState): DomainMessage {
  if (domain.routing === 'active' && !domain.serving) return {
    title: 'Domain unavailable', tone: 'danger',
    instruction: 'A required ownership, certificate or edge check is no longer valid. Use the fallback route and request a check.',
  };
  if (domain.routing === 'active') return {
    title: 'Domain active', tone: 'success', instruction: 'This hostname can serve this tenant.',
  };
  if (domain.routing === 'deactivated') return {
    title: 'Domain inactive', tone: 'warning', instruction: 'Use the fallback hostname or request recovery.',
  };
  if (domain.ownership === 'failed') return {
    title: 'Ownership needs attention', tone: 'warning', instruction: 'Correct the DNS proof and request another check.',
  };
  if (domain.tls === 'failed') return {
    title: 'Certificate needs attention', tone: 'danger', instruction: 'Check DNS and request another certificate check.',
  };
  if (domain.ownership !== 'verified') return {
    title: 'Verify ownership', tone: 'info', instruction: 'Add the DNS proof and request a check.',
  };
  if (domain.tls !== 'active') return {
    title: 'Securing domain', tone: 'info', instruction: 'Wait for certificate issuance.',
  };
  return {
    title: 'Awaiting activation', tone: 'info', instruction: 'A platform administrator must approve activation.',
  };
}
