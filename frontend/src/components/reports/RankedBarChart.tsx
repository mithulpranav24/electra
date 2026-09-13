import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface RankedBarChartProps {
  data: Array<{ label: string; value: number }>;
  emptyLabel: string;
  valueFormatter?: (value: number) => string;
}

export function RankedBarChart({ data, emptyLabel, valueFormatter }: RankedBarChartProps) {
  if (data.length === 0) {
    return <div className="flex h-56 items-center justify-center text-sm font-semibold text-[var(--steel)]">{emptyLabel}</div>;
  }

  const format = valueFormatter ?? ((value: number) => value.toLocaleString());

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 0, bottom: 4 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} stroke="var(--line)" strokeWidth={1} />
          <XAxis type="number" tick={{ fill: 'var(--steel)', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fill: 'var(--steel-dark)', fontSize: 12, fontWeight: 600 }}
            axisLine={false}
            tickLine={false}
            width={140}
          />
          <Tooltip
            formatter={(value) => [format(Number(value)), 'Count']}
            cursor={{ fill: 'var(--paper-muted)' }}
            contentStyle={{ borderRadius: 10, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {data.map((entry) => (
              <Cell key={entry.label} fill="var(--teal)" />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
