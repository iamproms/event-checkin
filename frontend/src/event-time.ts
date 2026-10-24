/** Convert event-local wall time to a unique UTC instant without using the device zone. */
const parts = (date: Date, zone: string) => {
  const format = new Intl.DateTimeFormat('en-GB', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  const values = Object.fromEntries(format.formatToParts(date).map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`;
};

export function eventLocal(instant: string, zone: string): string {
  return parts(new Date(instant), zone);
}

export function eventUtc(local: string, zone: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) {
    throw new Error('Enter a valid date and time.');
  }
  const [year, month, day, hour, minute] = local.match(/\d+/g)!.map(Number);
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  if (!Number.isFinite(wall)) throw new Error('Enter a valid date and time.');
  const matches: number[] = [];
  for (let offset = -12 * 60; offset <= 14 * 60; offset += 15) {
    const candidate = wall - offset * 60_000;
    if (parts(new Date(candidate), zone) === local) matches.push(candidate);
  }
  if (matches.length === 0) throw new Error('This local time does not occur in the selected time zone. Choose another time.');
  if (matches.length > 1) throw new Error('This local time repeats during a clock change. Choose another time or use the API with an explicit offset.');
  return new Date(matches[0]).toISOString();
}
