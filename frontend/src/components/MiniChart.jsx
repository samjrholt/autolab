import { motion } from "framer-motion";
import { buildSvgPath } from "../lib/helpers";
import { drawLine } from "../lib/motion";

export default function MiniChart({ points, width = 480, height = 200, className = "" }) {
  if (!points?.length) return null;
  const d = buildSvgPath(points, width, height);
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height }}
    >
      <motion.path
        d={d}
        className="chart-line"
        variants={drawLine}
        initial="hidden"
        animate="visible"
      />
    </svg>
  );
}
