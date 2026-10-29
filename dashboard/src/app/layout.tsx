import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Image Processor Arena — Pódio & Dashboard Analítico',
  description: 'Dashboard analítico interativo comparando implementações 100% puras de processamento de imagem em Go e Rust.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
