import type { Metadata } from "next";
import "@fontsource/lato/latin-400.css";
import "@fontsource/lato/latin-700.css";
import "./globals.css";

export const metadata: Metadata = { title: "DarGlobal Property Assistant" };

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
