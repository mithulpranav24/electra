import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

function formatHour(hour: number) {
  if (hour === 0) return '12am';
  if (hour === 12) return '12pm';
  return hour < 12 ? `${hour}am` : `${hour - 12}pm`;
}

export function PeakHoursChart({ data }: { data: Array<{ hour: number; count: number }> }) {
  const byHour = new Map(data.map((row) => [row.hour, row.count]));
  const filled = Array.from({ length: 24 }, (_, hour) => ({ hour, count: byHour.get(hour) ?? 0 }));
  const hasActivity = data.length > 0;

  if (!hasActivity) {
    return <div className="flex h-56 items-center justify-center text-sm font-semibold text-[var(--steel)]">No reservations in the last 30 days.</div>;
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={filled} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke="var(--line)" strokeWidth={1} />
          <XAxis dataKey="hour" tickFormatter={formatHour} tick={{ fill: 'var(--steel)', fontSize: 10 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} interval={2} />
          <YAxis tick={{ fill: 'var(--steel)', fontSize: 11 }} axisLine={false} tickLine={false} width={32} allowDecimals={false} />
          <Tooltip
            formatter={(value) => [Number(value).toLocaleString(), 'Reservations']}
            labelFormatter={(hour) => formatHour(Number(hour))}
            cursor={{ fill: 'var(--paper-muted)' }}
            contentStyle={{ borderRadius: 10, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
          />
          <Bar dataKey="count" fill="var(--teal)" radius={[4, 4, 0, 0]} maxBarSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
