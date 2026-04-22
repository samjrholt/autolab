import { motion } from "framer-motion";
import { fadeInUp } from "../lib/motion";

export default function MetricCard({ label, value, unit }) {
  return (
    <motion.div variants={fadeInUp} className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)]">
        {label}
      </span>
      <span className="text-[28px] font-semibold leading-none text-white">
        {value}
        {unit ? (
          <span className="ml-1.5 text-[12px] font-normal text-[var(--color-secondary)]">
            {unit}
          </span>
        ) : null}
      </span>
    </motion.div>
  );
}
