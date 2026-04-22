import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { slideIn } from "../lib/motion";

export default function SlideOver({ open, onClose, width = "max-w-lg", children }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="slide-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.aside
            className={`slide-panel w-full ${width}`}
            {...slideIn}
          >
            <div className="p-8">
              <button
                type="button"
                onClick={onClose}
                className="absolute top-6 right-6 text-[var(--color-secondary)] hover:text-white transition-colors bg-transparent border-none text-lg"
              >
                ✕
              </button>
              {children}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
