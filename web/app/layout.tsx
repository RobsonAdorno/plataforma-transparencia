import type { Metadata } from "next";
import { Archivo, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const titulo = Archivo({ subsets: ["latin"], weight: ["600", "700", "800"],
  variable: "--fonte-titulo", display: "swap" });
const corpo = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"],
  variable: "--fonte-corpo", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"],
  variable: "--fonte-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Transparência Política", template: "%s · Transparência Política" },
  description:
    "Quem foi eleito no Brasil, quanto gasta e como vota — a partir das fontes oficiais.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${titulo.variable} ${corpo.variable} ${mono.variable}`}>
      <body>
        <header className="topo">
          <div className="wrap">
            <Link href="/" className="marca">Transparência Política</Link>
            <nav>
              <Link href="/">Mapa</Link>
              <Link href="/congresso">Congresso</Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
