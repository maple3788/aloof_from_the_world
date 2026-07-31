import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aloof from the World",
  description:
    "Learn, study, and discuss philosophy, psychology, and history with the great thinkers — grounded in their actual texts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
