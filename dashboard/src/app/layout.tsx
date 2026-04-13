import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClinicalAgent-Bench Leaderboard",
  description: "Evaluation leaderboard for healthcare AI agents",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
