import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CRISIS-BENCH Dashboard",
  description: "Multi-agent disaster response coordination system for India",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 antialiased">{children}</body>
    </html>
  );
}
