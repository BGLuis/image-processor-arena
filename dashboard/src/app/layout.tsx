import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Image Processor Arena — Pódio & Dashboard Analítico',
  description: 'Dashboard analítico interativo e benchmark de processamento de imagem comparando implementações em 6 linguagens e 18 variantes.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans bg-[#0a0c0f] text-[#eceff3] antialiased selection:bg-[#2ec4e6]/30 selection:text-[#eceff3]`}>
        {children}
      </body>
    </html>
  );
}
