/** Shared framer-motion animation variants. */

export const fadeInUp = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

export const stagger = {
  visible: { transition: { staggerChildren: 0.05 } },
};

export const crossfade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2, ease: "easeIn" } },
};

export const slideIn = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.25, ease: "easeOut" } },
  exit: { opacity: 0, x: 24, transition: { duration: 0.2, ease: "easeIn" } },
};

export const drawLine = {
  hidden: { pathLength: 0 },
  visible: { pathLength: 1, transition: { duration: 0.8, ease: "easeOut" } },
};
