import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { eventApi, type EventSummary } from '../event-api';
import { safeErrorMessage } from '../safe-error';
import { readHashLocation } from './router';

type EventWorkspaceValue = {
  events: EventSummary[];
  loading: boolean;
  error: string;
  selectedEventId: string;
  selectedEvent?: EventSummary;
  setSelectedEventId: (eventId: string) => void;
  reload: () => Promise<void>;
};

const EventWorkspaceContext = createContext<EventWorkspaceValue | null>(null);

function preferredEvent(events: EventSummary[], requested: string) {
  return events.find(event => event.id === requested)?.id || events.find(event => event.status === 'published')?.id || events[0]?.id || '';
}

function replaceEventQuery(eventId: string) {
  const { route, params } = readHashLocation('dashboard');
  if (eventId) params.set('event', eventId);
  else params.delete('event');
  const query = params.toString();
  history.replaceState(history.state, '', `${location.pathname}${location.search}#${route}${query ? `?${query}` : ''}`);
}

export function EventWorkspaceProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEventId, setSelectedState] = useState(() => readHashLocation('dashboard').params.get('event') || '');

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setEvents(await eventApi.events()); }
    catch (cause) { setError(safeErrorMessage(cause, 'Events could not be loaded.')); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => {
    const updateFromUrl = () => setSelectedState(readHashLocation('dashboard').params.get('event') || '');
    addEventListener('hashchange', updateFromUrl);
    return () => removeEventListener('hashchange', updateFromUrl);
  }, []);
  useEffect(() => {
    if (loading) return;
    const next = preferredEvent(events, selectedEventId);
    if (next !== selectedEventId) setSelectedState(next);
    const urlEvent = readHashLocation('dashboard').params.get('event') || '';
    if (urlEvent !== next) replaceEventQuery(next);
  }, [events, loading, selectedEventId]);

  const setSelectedEventId = useCallback((eventId: string) => {
    const next = preferredEvent(events, eventId);
    setSelectedState(next);
    replaceEventQuery(next);
  }, [events]);
  const selectedEvent = events.find(event => event.id === selectedEventId);
  const value = useMemo(() => ({ events, loading, error, selectedEventId, selectedEvent, setSelectedEventId, reload }), [events, loading, error, selectedEventId, selectedEvent, setSelectedEventId, reload]);
  return <EventWorkspaceContext.Provider value={value}>{children}</EventWorkspaceContext.Provider>;
}

export function useEventWorkspace() {
  const value = useContext(EventWorkspaceContext);
  if (!value) throw new Error('useEventWorkspace must be used inside EventWorkspaceProvider');
  return value;
}
