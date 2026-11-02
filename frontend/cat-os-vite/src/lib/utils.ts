import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge the terminal type scale (globals.css --text-t1..t4) so a
// `text-t3` passed via className still overrides a primitive's `text-sm`,
// exactly as the arbitrary 11px value it replaced did.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["t1", "t2", "t3", "t4"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
