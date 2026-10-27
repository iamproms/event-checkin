import { useEffect, useState } from 'react';

type PublicBrand = { display_name: string; logo_url: string | null; revision: number };

export function TenantBrandMark({ area }: { area: string }) {
  const [brand, setBrand] = useState<PublicBrand | null>(null);
  useEffect(() => {
    void fetch('/api/v1/branding/public', { cache: 'no-store', credentials: 'same-origin' })
      .then((response) => response.ok ? response.json() as Promise<PublicBrand> : null)
      .then((result) => { if (result) setBrand(result); })
      .catch(() => { /* Keep the readable platform fallback. */ });
  }, []);
  return <span className="tenant-brand-mark">
    {brand?.logo_url && <img src={brand.logo_url} alt="" className="tenant-brand-mark__logo" />}
    <a href="/workspace.html">{brand?.display_name || 'Event Check-in'}</a><span aria-hidden="true">/</span><span>{area}</span>
  </span>;
}
