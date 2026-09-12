import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { RevenueByDay } from '../../types';
import { formatCurrency } from '../../lib/format';

function formatDayLabel(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function RevenueTrendChart({ data }: { data: RevenueByDay[] }) {
  if (data.length === 0) {
    return <div className="flex h-56 items-center justify-center text-sm font-semibold text-[var(--steel)]">No paid invoices in this window yet.</div>;
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--teal)" stopOpacity={0.16} />
              <stop offset="100%" stopColor="var(--teal)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--line)" strokeWidth={1} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDayLabel}
            tick={{ fill: 'var(--steel)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--line)' }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: 'var(--steel)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={56}
            tickFormatter={(value: number) => formatCurrency(value, 0)}
          />
          <Tooltip
            formatter={(value) => [formatCurrency(Number(value)), 'Revenue']}
            labelFormatter={(label) => formatDayLabel(String(label))}
            contentStyle={{ borderRadius: 10, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
          />
          <Area type="monotone" dataKey="revenue" stroke="var(--teal)" strokeWidth={2} fill="url(#revenueFill)" activeDot={{ r: 4, stroke: 'var(--paper)', strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
