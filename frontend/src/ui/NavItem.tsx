import type { AnchorHTMLAttributes, ReactNode } from 'react';

export interface NavItemProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  current?: boolean;
  children: ReactNode;
}

export function NavItem({ current = false, className = '', children, ...props }: NavItemProps) {
  return <a {...props} aria-current={current ? 'page' : undefined} className={`ui-nav-item${current ? ' ui-nav-item--current' : ''} ${className}`.trim()}>{children}</a>;
}
