import type { SVGProps } from 'react';

export type IconName = 'overview' | 'organizations' | 'domains' | 'billing' | 'operations' | 'settings' |
  'events' | 'attendees' | 'tickets' | 'checkin' | 'messages' | 'reports' | 'team' | 'search' |
  'menu' | 'close' | 'moon' | 'sun' | 'arrow' | 'plus' | 'shield' | 'camera' | 'warning' | 'help';

const paths: Record<IconName, React.ReactNode> = {
  overview: <><path d="M4 4h6v6H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 14h6v6H4z" /></>,
  organizations: <><path d="M4 20V7l8-3 8 3v13M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M9 20v-3h6v3" /></>,
  domains: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" /></>,
  billing: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h3" /></>,
  operations: <><path d="M4 16l4-5 4 3 4-7 4 3M4 20h16" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19 13.5v-3l-2-.7-.5-1.2.9-1.9-2.1-2.1-1.9.9-1.2-.5L10.5 3h-3L6.8 5l-1.2.5-1.9-.9-2.1 2.1.9 1.9-.5 1.2-2 .7v3l2 .7.5 1.2-.9 1.9 2.1 2.1 1.9-.9 1.2.5.7 2h3l.7-2 1.2-.5 1.9.9 2.1-2.1-.9-1.9.5-1.2z" /></>,
  events: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18M7 14h3M7 17h7" /></>,
  attendees: <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="10" r="2" /><path d="M3 20c0-4 2-7 6-7s6 3 6 7M15 15c3 0 5 2 5 5" /></>,
  tickets: <><path d="M4 5h16v5a2 2 0 0 0 0 4v5H4v-5a2 2 0 0 0 0-4zM12 7v10" /></>,
  checkin: <><path d="M4 12l5 5L20 6" /></>,
  messages: <><path d="M4 5h16v12H8l-4 3z" /></>,
  reports: <><path d="M5 3h10l4 4v14H5zM15 3v5h4M8 17v-3M12 17v-6M16 17v-4" /></>,
  team: <><circle cx="8" cy="9" r="3" /><circle cx="17" cy="8" r="2" /><path d="M2 20c0-4 2-7 6-7s6 3 6 7M14 13c4 0 7 2 7 6" /></>,
  search: <><circle cx="10" cy="10" r="6" /><path d="M15 15l5 5" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>, close: <><path d="M6 6l12 12M18 6L6 18" /></>,
  moon: <path d="M20 15a8 8 0 0 1-11-11 9 9 0 1 0 11 11z" />, sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>, plus: <><path d="M12 5v14M5 12h14" /></>,
  shield: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM8.5 12l2.2 2.2 4.8-5" /></>,
  camera: <><path d="M3 8h4l2-3h6l2 3h4v11H3z" /><circle cx="12" cy="13" r="4" /></>,
  warning: <><path d="M12 3l10 18H2zM12 9v5M12 17h.01" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.7 9a2.5 2.5 0 1 1 3.3 2.4c-.8.3-1 1-1 1.6M12 17h.01" /></>,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
