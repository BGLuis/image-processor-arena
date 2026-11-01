import type { Metadata } from 'next';
import { Archivo, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { ThemeProvider } from '../context/ThemeContext';

const archivo = Archivo({
  variable: '--font-archivo',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Image Processor Arena — Ficha de Cronometragem & Dashboard Analítico',
  description: 'Ficha de cronometragem analítica e benchmark de processamento de imagem de alta performance comparando Pure Go vs Pure Rust.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var t = localStorage.getItem('arena_theme') || 'system';
                  var isDark = t === 'dark' || (t !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                  if (isDark) {
                    document.documentElement.classList.add('dark');
                    document.documentElement.setAttribute('data-theme', 'dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.setAttribute('data-theme', 'light');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className={`${archivo.variable} ${jetbrainsMono.variable} font-sans antialiased selection:bg-[#E0703A]/20 selection:text-[#E0703A]`}>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
