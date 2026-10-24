import type { StatusTone } from './ui/Status';

export type EventState = 'draft' | 'published' | 'closed' | 'cancelled';
export type EventMessage = { title: string; tone: StatusTone; instruction: string };

/** M2-03/G-01 vocabulary v1. Keep state meaning outside presentation primitives. */
export function describeEvent(state: EventState): EventMessage {
  const messages: Record<EventState, EventMessage> = {
    draft: { title: 'Draft', tone: 'info', instruction: 'Complete setup and review readiness before publishing.' },
    published: { title: 'Published', tone: 'success', instruction: 'The published schedule and form are fixed.' },
    closed: { title: 'Closed', tone: 'warning', instruction: 'This event cannot reopen in v1.' },
    cancelled: { title: 'Cancelled', tone: 'danger', instruction: 'Cancellation is final. This event cannot reopen.' },
  };
  return messages[state];
}
