import { useEffect, useState } from 'react';

export function readHashLocation(fallback: string) {
  const raw = location.hash.replace(/^#\/?/, '');
  const [route, query = ''] = raw.split('?');
  return { route: route || fallback, params: new URLSearchParams(query) };
}

export function useHashRoute(fallback: string) {
  const read = () => readHashLocation(fallback).route;
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const update = () => setRoute(read());
    addEventListener('hashchange', update);
    return () => removeEventListener('hashchange', update);
  }, []);
  return route;
}

export function routeHref(route: string, changes?: Record<string, string | null>) {
  const params = typeof location === 'undefined' ? new URLSearchParams() : readHashLocation(route).params;
  for (const [key, value] of Object.entries(changes || {})) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  return `#${route}${query ? `?${query}` : ''}`;
}
