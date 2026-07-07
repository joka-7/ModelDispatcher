/** Root layout for the App Router template. */

import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "ModelDispatcher — Vercel template",
  description: "Resilient AI gateway integration with Firebase App Check.",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
