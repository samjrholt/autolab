import { cn, statusColor } from "../lib/helpers";

export default function StatusIndicator({ status, pulse = false, className }) {
  const color = statusColor(status);
  return (
    <span
      className={cn(
        "status-dot",
        `status-dot--${color}`,
        pulse && "status-dot--pulse",
        className,
      )}
      title={status}
    />
  );
}
