import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Whiteboard Video Generator",
  description: "Generate educational whiteboard explainer videos locally",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
