import { useEffect, useState } from 'react';

export function useHashRoute(fallback: string) {
  const read = () => location.hash.replace(/^#\/?/, '').split('?')[0] || fallback;
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const update = () => setRoute(read());
    addEventListener('hashchange', update);
    return () => removeEventListener('hashchange', update);
  }, []);
  return route;
}

export function routeHref(route: string) {
  return `#${route}`;
}
