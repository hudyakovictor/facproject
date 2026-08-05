import React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ShieldCheck, CheckCircle2, Download, ExternalLink, Activity, X, Database } from "lucide-react";

interface EvidenceLinkModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  photoId: string;
  date: string;
  snr: number;
  snrDelta: number;
  sha256: string;
  ipfsCid: string;
  csvSnippet: string;
}

export const EvidenceLinkModal: React.FC<EvidenceLinkModalProps> = ({
  isOpen,
  onOpenChange,
  title,
  photoId,
  date,
  snr,
  snrDelta,
  sha256,
  ipfsCid,
  csvSnippet,
}) => {
  const handleDownloadCsv = () => {
    const blob = new Blob([csvSnippet], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", `${photoId}_evidence_bundle.csv`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[#080d12]/80 backdrop-blur-sm z-50 animate-fade-in" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg rounded-xl border border-cyan-800/80 bg-[#0b1117] p-6 shadow-2xl z-50 text-[#e2e8f0] font-sans">
          <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-3 mb-4">
            <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
              <ShieldCheck className="h-5 w-5 text-cyan-400" />
              <span>ИНТЕРАКТИВНОЕ ДОКАЗАТЕЛЬСТВО: {photoId}</span>
            </div>
            <Dialog.Close asChild>
              <button className="text-slate-500 hover:text-white transition">
                <X className="h-5 w-5" />
              </button>
            </Dialog.Close>
          </div>

          <div className="space-y-4 font-mono text-xs">
            <div className="rounded-lg bg-[#101820] p-4 border border-[#1f2d3d] space-y-2">
              <div className="text-sm font-bold text-white">{title}</div>
              <div className="flex items-center justify-between text-slate-300 pt-1 border-t border-[#1f2d3d]">
                <span>Дата EXIF:</span>
                <span className="text-cyan-300 font-bold">{date}</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Костный SNR 3DDFA_v3:</span>
                <span className="text-emerald-400 font-bold">{snr} HIGH</span>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Отклонение от эталона (ΔSNR):</span>
                <span className="text-amber-400 font-bold">{snrDelta}</span>
              </div>
            </div>

            {/* Cryptographic Hashes */}
            <div className="rounded-lg bg-[#141e27] p-4 border border-cyan-900/60 space-y-2">
              <div className="font-bold text-cyan-300 uppercase mb-1 flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <span>Криптографическая верификация SHA-256</span>
              </div>
              <div>
                <span className="text-slate-400">SHA-256 файла:</span>
                <div className="text-emerald-300 truncate mt-0.5">{sha256}</div>
              </div>
              <div>
                <span className="text-slate-400">IPFS CID:</span>
                <div className="text-cyan-400 truncate mt-0.5">{ipfsCid}</div>
              </div>
            </div>

            {/* Download CSV Snippet */}
            <div className="pt-2 flex items-center justify-between">
              <button
                onClick={handleDownloadCsv}
                className="rounded bg-cyan-600 px-4 py-2 font-bold text-white hover:bg-cyan-500 transition shadow-lg shadow-cyan-950 flex items-center gap-2"
              >
                <Download className="h-4 w-4" />
                <span>Скачать CSV фрагмент измерений</span>
              </button>

              <span className="text-[11px] text-slate-500">
                100% ВЕРСИЯ STAGE 1
              </span>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
