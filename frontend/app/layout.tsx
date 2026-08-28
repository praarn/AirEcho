import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "AirEcho – personal air-quality health risk",
  description:
    "AirEcho ties your own lagged pollution exposure to your own symptom pattern, with grounded WHO/CPCB advisory. Honest about irregular data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
