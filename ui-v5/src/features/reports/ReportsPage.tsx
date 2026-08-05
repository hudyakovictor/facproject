import React, { useState } from "react";
import { FileText, ExternalLink, ShieldCheck, AlertTriangle, Eye, CheckCircle2, Download } from "lucide-react";

export const ReportsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"tech" | "internal" | "public">("tech");
  const [skepticOpen, setSkepticOpen] = useState<boolean>(true);

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6 font-sans">
      {/* HEADER: JOURNALIST PUBLICATION SUITE */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/80 bg-[#0b1117] p-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
            <FileText className="h-5 w-5 text-cyan-400" />
            ПУБЛИКАЦИОННЫЙ РЕДАКТОР ЖУРНАЛИСТА (EVIDENCELINK &amp; ПАНЕЛЬ «СКЕПТИК»)
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Сплит-редактор: каждый тезис статьи жестко связан с криптографическим доказательством (SHA-256 / SNR)
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <button className="rounded bg-[#101820] px-3 py-1.5 text-slate-300 border border-[#1f2d3d] hover:bg-[#18232d] transition">
            [проверить факты]
          </button>
          <button className="rounded bg-cyan-600 px-3 py-1.5 text-white font-bold hover:bg-cyan-500 transition shadow-lg shadow-cyan-950 flex items-center gap-1.5">
            <Download className="h-4 w-4" />
            <span>Экспорт Immutable Bundle</span>
          </button>
        </div>
      </div>

      {/* DRAFT MODE TABS */}
      <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 font-mono text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("tech")}
            className={`rounded px-3 py-1.5 transition ${
              activeTab === "tech"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Технический отчет (Для биометристов)
          </button>
          <button
            onClick={() => setActiveTab("internal")}
            className={`rounded px-3 py-1.5 transition ${
              activeTab === "internal"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Внутреннее досье (Для редакции)
          </button>
          <button
            onClick={() => setActiveTab("public")}
            className={`rounded px-3 py-1.5 transition ${
              activeTab === "public"
                ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Публичная статья для СМИ (DEEPUTIN)
          </button>
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-slate-300">
          <input
            type="checkbox"
            checked={skepticOpen}
            onChange={(e) => setSkepticOpen(e.target.checked)}
            className="accent-amber-500 h-4 w-4"
          />
          <span>Показать панель «Скептик» (Альтернативные объяснения)</span>
        </label>
      </div>

      {/* MAIN SPLIT EDITOR: ARTICLE TEXT (70%) + SKEPTIC PANEL (30%) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ARTICLE TEXT CONTENT */}
        <div className="lg:col-span-2 rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-6 space-y-4">
          <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between font-mono text-xs">
            <span className="font-bold text-slate-200">
              ЧЕРНОВИК: ХРОНОЛОГИЯ СТАБИЛЬНОСТИ ЛИЦА 1999–2026
            </span>
            <span className="text-emerald-400">FAIR USE COMPLIANT</span>
          </div>

          <div className="space-y-4 text-sm text-slate-300 leading-relaxed">
            <p>
              Анализ архива из 1,900 фотографий Владимира Путина с 1999 по 2026 год, выполненный нейросетевым комплексом{" "}
              <strong className="text-white">3DDFA_v3</strong> на основе анатомической сетки Basel Face Model, подтверждает,
              что костные структуры лица претерпевают естественные возрастные изменения по монотонной кривой старения на
              интервалах{" "}
              <span className="inline-flex items-center gap-1 rounded bg-cyan-950 px-1.5 py-0.5 font-mono text-xs text-cyan-300 border border-cyan-800">
                1999–2007 (SNR 18.2) <ExternalLink className="h-3 w-3 inline" />
              </span>{" "}
              и{" "}
              <span className="inline-flex items-center gap-1 rounded bg-cyan-950 px-1.5 py-0.5 font-mono text-xs text-cyan-300 border border-cyan-800">
                2012–2014 (SNR 17.8) <ExternalLink className="h-3 w-3 inline" />
              </span>.
            </p>

            <p>
              Однако в период <strong className="text-amber-300">мая 2008 – октября 2010 годов</strong> фиксируется
              статистически значимый хронологический разрыв (Step-Change) в геометрии скуловых дуг и межглазничного
              расстояния{" "}
              <span className="inline-flex items-center gap-1 rounded bg-amber-950 px-1.5 py-0.5 font-mono text-xs text-amber-300 border border-amber-800">
                [A = 2008-05-07 vs B = 2010-10-25] ΔSNR = 2.48 <ExternalLink className="h-3 w-3 inline" />
              </span>. Впоследствии костные пропорции демонстрируют парадоксальный возврат к базовой линии 1999 года.
            </p>

            <p>
              В соответствии с протоколом антропологической экспертизы (LOPO FDR ≤ 0.05), данные результаты не являются
              автоматическим вердиктом о личности, а представляют собой биометрическое доказательство для журналистской и
              редакционной верификации.
            </p>
          </div>
        </div>

        {/* SKEPTIC PANEL (30% RIGHT AREA) */}
        {skepticOpen && (
          <div className="rounded-lg border border-amber-800/80 bg-[#0b1117] p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div className="border-b border-[#1f2d3d] pb-2 mb-3 flex items-center justify-between font-mono text-xs">
                <span className="font-bold text-amber-300 uppercase flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  ПАНЕЛЬ «СКЕПТИК»
                </span>
                <span className="text-[10px] text-slate-400">ФАКТ-ЧЕКИНГ</span>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="rounded bg-[#101820] p-3 border border-amber-900/50">
                  <div className="font-bold text-amber-300 mb-1">Критика: «Искажение объектива 2008 г.»</div>
                  <p className="text-slate-300 text-[11px] font-sans">
                    Различие в форме носа на снимке 2008-05-07 может объясняться использованием короткофокусного объектива
                    28 мм на пресс-конференции. В расчете 3DDFA_v3 применена ортографическая коррекция.
                  </p>
                </div>

                <div className="rounded bg-[#101820] p-3 border border-amber-900/50">
                  <div className="font-bold text-amber-300 mb-1">Критика: «Косметические процедуры»</div>
                  <p className="text-slate-300 text-[11px] font-sans">
                    Сглаживание высокочастотного спектра лба в 2010 году может являться следствием инъекций ботулотоксина,
                    поэтому зона лба исключена из костного сравнения.
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-[#1f2d3d] font-mono text-[11px] text-slate-400 text-center">
              Гарантия объективности расследования
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
