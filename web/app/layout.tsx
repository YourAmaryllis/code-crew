import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "code-crew — Virtual AI Development Team",
  description:
    "CrewAI-based multi-agent crew for the full software development lifecycle. Sprint planning, architecture, BDD, security, compliance, and Definition of Done — driven by your issue tracker and your own knowledge base.",
  openGraph: {
    title: "code-crew — Virtual AI Development Team",
    description:
      "Eight specialised AI agents covering the full SDLC: sprint planning → architecture → BDD → implementation → security → compliance → staging.",
    url: "https://code-crew.youramaryllis.com",
    siteName: "code-crew",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
