const tones = {
  blue: "border-cobalt/60 text-cobalt shadow-glow-cobalt/10 bg-cobalt/5",
  green: "border-mint/60 text-mint shadow-glow-mint/10 bg-mint/5",
  amber: "border-saffron/60 text-saffron shadow-glow-saffron/10 bg-saffron/5",
  red: "border-ember/60 text-ember shadow-glow-ember/10 bg-ember/5",
  purple: "border-lilac/60 text-lilac shadow-glow-lilac/10 bg-lilac/5",
};

function StatCard({ label, value, color }) {
  return (
    <div className={`glass-panel grain flex flex-col gap-2 border-l-4 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98] ${tones[color]}`}>
      <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">{label}</span>
      <span className="font-mono text-3xl font-extrabold text-paper tracking-tight">{value}</span>
    </div>
  );
}

export default function StatBar({ stats }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-5">
      <StatCard label="Total Transactions" value={stats.total_transactions} color="blue" />
      <StatCard label="Allowed" value={stats.allowed} color="green" />
      <StatCard label="Step-Up Auth" value={stats.step_up} color="amber" />
      <StatCard label="Blocked" value={stats.blocked} color="red" />
      <StatCard label="Block Rate" value={`${stats.block_rate}%`} color="purple" />
    </div>
  );
}

