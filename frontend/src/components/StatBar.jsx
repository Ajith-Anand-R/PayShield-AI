import { CreditCard, ShieldCheck, Fingerprint, ShieldAlert, Percent } from "lucide-react";

export default function StatBar({ stats }) {
  const items = [
    {
      label: "Total Scored",
      value: stats.total_transactions,
      color: "text-paper",
      glowColor: "rgba(248, 250, 252, 0.05)",
      icon: CreditCard,
      iconColor: "text-mist",
    },
    {
      label: "Approved",
      value: stats.allowed,
      color: "text-mint",
      glowColor: "rgba(16, 185, 129, 0.08)",
      icon: ShieldCheck,
      iconColor: "text-mint",
    },
    {
      label: "Step-Up Auth",
      value: stats.step_up,
      color: "text-saffron",
      glowColor: "rgba(251, 146, 60, 0.08)",
      icon: Fingerprint,
      iconColor: "text-saffron",
    },
    {
      label: "Blocked",
      value: stats.blocked,
      color: "text-rose-400",
      glowColor: "rgba(244, 63, 94, 0.08)",
      icon: ShieldAlert,
      iconColor: "text-rose-400",
    },
    {
      label: "Block Rate",
      value: `${stats.block_rate}%`,
      color: "text-cobalt",
      glowColor: "rgba(59, 130, 246, 0.08)",
      icon: Percent,
      iconColor: "text-cobalt",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
      {items.map((item, idx) => {
        const Icon = item.icon;
        return (
          <div
            key={idx}
            style={{
              boxShadow: `0 8px 32px 0 rgba(0, 0, 0, 0.2), 0 0 15px ${item.glowColor}`,
            }}
            className="rounded-2xl border border-white/5 bg-carbon/30 backdrop-blur-xl px-5 py-4.5 flex flex-col justify-between transition-all duration-300 hover:-translate-y-0.5 hover:border-white/10 group"
          >
            <div className="flex items-center justify-between">
              <span className="text-[9px] uppercase tracking-[0.2em] text-mist font-bold">
                {item.label}
              </span>
              <Icon className={`h-4 w-4 ${item.iconColor} opacity-75 group-hover:scale-110 transition-transform duration-300`} />
            </div>
            <p className={`font-mono text-2.5xl font-black ${item.color} mt-3`}>
              {item.value}
            </p>
          </div>
        );
      })}
    </div>
  );
}
