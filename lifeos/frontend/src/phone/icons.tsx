// Small rounded line icons for the phone app (original, drawn on a 24px grid).
import React from "react";

const P: Record<string, React.ReactNode> = {
  story: <><path d="M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4z" /><path d="M9 9h6M9 13h4" /></>,
  phone: <><rect x="6" y="2.5" width="12" height="19" rx="3" /><path d="M10.5 18.5h3" /></>,
  home: <><path d="M3.5 11 12 4l8.5 7" /><path d="M6 9.5V20h12V9.5" /><path d="M10 20v-5h4v5" /></>,
  me: <><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></>,
  heart: <path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z" />,
  bolt: <path d="M13 2 5 13h6l-1 9 8-11h-6z" />,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z" /><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5" /></>,
  ball: <><circle cx="12" cy="12" r="8.5" /><path d="M5 7.5c3 1.5 4 6 3 10M19 7.5c-3 1.5-4 6-3 10" /></>,
  moon: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />,
  star: <path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" />,
  people: <><circle cx="9" cy="8" r="3.2" /><path d="M2.8 19c.9-3.2 3.2-5 6.2-5s5.3 1.8 6.2 5" /><circle cx="17" cy="9" r="2.6" /><path d="M16.5 14.2c2.4.2 4 1.7 4.7 4.3" /></>,
  work: <><rect x="3.5" y="7" width="17" height="12" rx="2.5" /><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3.5 12h17" /></>,
  warn: <><path d="M12 3.5 2.5 20h19z" /><path d="M12 10v4.5M12 17.2v.3" /></>,
  paw: <><circle cx="7" cy="10" r="1.8" /><circle cx="10.5" cy="6.5" r="1.8" /><circle cx="14.5" cy="6.5" r="1.8" /><circle cx="18" cy="10" r="1.8" /><path d="M12.5 11.5c-3 0-5.5 3.2-5.5 5.3 0 1.6 1.3 2.2 2.6 2.2 1.2 0 1.9-.6 2.9-.6s1.7.6 2.9.6c1.3 0 2.6-.6 2.6-2.2 0-2.1-2.5-5.3-5.5-5.3z" /></>,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  back: <path d="m15 5-7 7 7 7" />,
  sparkle: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /><path d="m6.5 6.5 2 2M15.5 15.5l2 2M17.5 6.5l-2 2M8.5 15.5l-2 2" /></>,
  flame: <path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.9 3.6-6 4-10.3 2.6 1.6 4 4 4.1 6.3.9-.7 1.4-1.8 1.5-3 2.3 1.9 3.4 4.4 3.4 7 0 3.6-2.6 6.2-6.5 6.2z" />,
  bone: <path d="M7 9.5a2.5 2.5 0 1 1 2.5-4L14.5 10.5a2.5 2.5 0 1 1 4 2.5 2.5 2.5 0 1 1-2.5 4l-5-5a2.5 2.5 0 1 1-4-2.5z" />,
  bowl: <><path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0z" /><path d="M8 8.5c0-1.2 1-1.2 1-2.5M12 8.5c0-1.2 1-1.2 1-2.5M16 8.5c0-1.2 1-1.2 1-2.5" /></>,
  brush: <><path d="M14 4.5 19.5 10 11 18.5H5.5V13z" /><path d="m11.5 7 5.5 5.5" /></>,
  tree: <><path d="M12 3c3.5 0 6 2.6 6 5.5 0 1-.3 1.9-.8 2.6A4.5 4.5 0 0 1 14 18.5h-4A4.5 4.5 0 0 1 6.8 11a4.8 4.8 0 0 1-.8-2.5C6 5.6 8.5 3 12 3z" /><path d="M12 13v8" /></>,
  ballplay: <><circle cx="12" cy="12" r="7.5" /><path d="M5.5 9.5c4 .8 9 .8 13 0M5.5 14.5c4-.8 9-.8 13 0" /></>,
  wand: <><path d="m4 20 10-10M14 10l2-2" /><path d="M17 3v3M20.5 6.5h-3M17.5 9.5l2 2M12 4.5l1.5 1.5" /></>,
  walk: <><circle cx="13" cy="4.5" r="2" /><path d="m10 21 2-6 3 3v3M8.5 11.5 11 8.5l4 1.5 2 3.5M11 8.5 10 14" /></>,
  chat: <path d="M4.5 5.5h15v10h-9l-4.5 4v-4h-1.5z" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  skip: <><path d="M5 5.5 13 12l-8 6.5z" /><path d="M13 5.5 21 12l-8 6.5z" /></>,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  cash: <><rect x="3" y="6.5" width="18" height="11" rx="2.5" /><circle cx="12" cy="12" r="2.6" /></>,
  grad: <><path d="M2.5 9 12 5l9.5 4L12 13z" /><path d="M6.5 11v4.5c1.5 1.3 3.3 2 5.5 2s4-.7 5.5-2V11" /></>,
  trophy: <><path d="M8 4h8v5a4 4 0 0 1-8 0z" /><path d="M8 6H4.5a3 3 0 0 0 3.5 4M16 6h3.5a3 3 0 0 1-3.5 4M12 13v4M8.5 20h7" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  download: <><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5" /><path d="M4.5 19.5h15" /></>,
  upload: <><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" /><path d="M4.5 19.5h15" /></>,
  laptop: <><rect x="4.5" y="5" width="15" height="10" rx="1.5" /><path d="M2.5 19h19" /></>,
  family: <><circle cx="8" cy="7" r="2.6" /><circle cx="16" cy="7" r="2.6" /><circle cx="12" cy="13" r="2" /><path d="M3.5 19c.5-3.4 2.2-5.6 4.5-5.6M20.5 19c-.5-3.4-2.2-5.6-4.5-5.6M9 20c.4-2 1.5-3.2 3-3.2s2.6 1.2 3 3.2" /></>,
  leaf: <><path d="M5 19c0-8 5.5-13 15-14-1 9.5-6 15-14 15z" /><path d="M5 19 13 11" /></>,
};

export function PIcon({ name, size = 20, stroke = 2, className, fill }: { name: string; size?: number; stroke?: number; className?: string; fill?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill={fill || "none"} stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {P[name] || P.star}
    </svg>
  );
}
