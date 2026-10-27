import { useEffect, useState, type ReactNode } from 'react';
import { ThemeControl } from '../ui';
import { Icon, type IconName } from './icons';
import { routeHref } from './router';

export type NavItem = { route: string; label: string; icon: IconName; badge?: string };

type Props = {
  product: string;
  context: string;
  route: string;
  nav: NavItem[];
  children: ReactNode;
  utility?: ReactNode;
};

export function AppShell({ product, context, route, nav, children, utility }: Props) {
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => setNavOpen(false), [route]);
  const current = nav.find((item) => item.route === route);
  return <div className="app-frame">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="app-topbar">
      <button className="icon-button mobile-menu" onClick={() => setNavOpen(true)} aria-label="Open navigation"><Icon name="menu" /></button>
      <a className="wordmark" href={routeHref(nav[0].route)} aria-label={`${product} home`}><span className="wordmark-mark">E</span><span>{product}</span></a>
      <div className="topbar-actions">{utility}<ThemeControl compact /></div>
    </header>
    {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    <aside className={`app-sidebar${navOpen ? ' is-open' : ''}`} aria-label={`${context} navigation`}>
      <div className="sidebar-context"><span>{context}</span><button className="icon-button mobile-menu" onClick={() => setNavOpen(false)} aria-label="Close navigation"><Icon name="close" /></button></div>
      <nav>{nav.map((item) => <a key={item.route} href={routeHref(item.route)} className={item.route === route ? 'is-current' : ''} aria-current={item.route === route ? 'page' : undefined}><Icon name={item.icon} /><span>{item.label}</span>{item.badge && <small>{item.badge}</small>}</a>)}</nav>
      <div className="sidebar-footer"><a href="#help"><Icon name="help" /><span>Help and support</span></a><p>Secure local workspace</p></div>
    </aside>
    <main className="app-sheet" id="main-content" tabIndex={-1}>
      <div className="mobile-title"><span>{current?.label || context}</span></div>
      {children}
    </main>
  </div>;
}
