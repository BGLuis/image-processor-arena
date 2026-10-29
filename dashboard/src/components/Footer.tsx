'use client';

import React from 'react';

export default function Footer() {
  return (
    <footer className="w-full border-t border-[#222831] py-8 mt-12 bg-[#0a0c0f] text-center text-xs text-[#6b7480]">
      <div className="max-w-[1400px] mx-auto px-4 space-y-1.5">
        <p className="text-[#a3acb9]">
          Image Processor Arena · implementações de processamento de imagem · AGPL-3.0-or-later
        </p>
        <p className="font-mono text-[11px] text-[#6b7480]">
          Motor analítico in-browser: DuckDB-Wasm + Next.js
        </p>
      </div>
    </footer>
  );
}
