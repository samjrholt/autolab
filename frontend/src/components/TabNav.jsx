import { cn } from "../lib/helpers";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "campaign", label: "Campaign" },
  { id: "provenance", label: "Provenance" },
];

export default function TabNav({ active, onChange }) {
  return (
    <nav className="flex items-center gap-8">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            "relative bg-transparent border-none pb-2 text-[13px] font-medium tracking-[0.06em] transition-colors",
            active === tab.id
              ? "text-white"
              : "text-[var(--color-secondary)] hover:text-white",
          )}
        >
          {tab.label}
          {active === tab.id && (
            <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-white rounded-full" />
          )}
        </button>
      ))}
    </nav>
  );
}
