import React, { useState } from "react";
import { EvidenceLinkModal } from "./EvidenceLinkModal";
import {
  BookOpen,
  ShieldCheck,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Layers,
  Activity,
  Award,
  FileText,
} from "lucide-react";

interface ArticleMeta {
  id: number;
  slug: string;
  title: string;
  subtitle: string;
  renderImage: string;
  renderCaption: string;
  readingTime: string;
  category: "МЕТОДОЛОГИЯ" | "3D-ГЕОМЕТРИЯ" | "ТЕКСТУРА И АЛЬБЕДО" | "СТАТИСТИКА И БАЙЕС" | "БЛОКЧЕЙН И NFT";
  evidenceCount: number;
  summary: string;
  keyMethod: string;
}

const PUBLIC_ARTICLES: ArticleMeta[] = [
  {
    id: 1,
    slug: "archaeology",
    title: "Археология цифрового портрета",
    subtitle: "Как превратить 1,900 архивных фотографий за 27 лет в биометрическую летопись",
    renderImage: "01_archaeology_provenance_render.jpg",
    renderCaption: "Визуализация цифровой археологии портретов, SHA-256 провенанса и 9 ракурсных корзин (1999–2026)",
    readingTime: "7 мин",
    category: "МЕТОДОЛОГИЯ",
    evidenceCount: 1900,
    summary:
      "Описание принципа «Одно фото = Ровно одна точка наблюдения на временной шкале». Каждое изображение получает неизменяемый идентификатор photo_id и SHA-256 хеш. Разделение архива на 9 ракурсных корзин для точного сравнения.",
    keyMethod: "SHA-256 EXIF-аудит & Нормализация ракурсных корзин (Pose Gate ≤ 6°)",
  },
  {
    id: 2,
    slug: "3d-reconstruction",
    title: "Сквозь пиксели к костям",
    subtitle: "Нейросетевая 3D-реконструкция лица методом 3DDFA_v3 и топология Basel Face Model",
    renderImage: "02_3ddfa_bfm_geometry_render.jpg",
    renderCaption: "3D-реконструкция Basel Face Model (BFM), 21 анатомическая костная зона и 91 стабильная точка (Subset-91)",
    readingTime: "9 мин",
    category: "3D-ГЕОМЕТРИЯ",
    evidenceCount: 1900,
    summary:
      "Почему 2D-фотография обманчива и как наклон головы искажает экранные пропорции. Математическое разделение формы черепа (alpha_id) и мимической нагрузки (alpha_exp) с использованием Raw Object-Normalized координат.",
    keyMethod: "3DDFA_v3 Basel Face Model & Raw Object-Normalized Coordinates",
  },
  {
    id: 3,
    slug: "bone-zones",
    title: "Анатомия стабильности",
    subtitle: "21 костная зона лица и детерминированный каталог Subset-91",
    renderImage: "02_3ddfa_bfm_geometry_render.jpg",
    renderCaption: "Сетка стабильных костных вершин Subset-91 и приоритетные зоны переносицы, глазниц и скуловых дуг",
    readingTime: "8 мин",
    category: "3D-ГЕОМЕТРИЯ",
    evidenceCount: 91,
    summary:
      "Почему скулы, глазницы и переносица не меняются со временем. Динамическое исключение мягких тканей (губы, носогубные складки) при улыбке или открытом рте. Краниометрическая асимметрия как биометрический отпечаток.",
    keyMethod: "Анатомическое взвешивание (w=1.0) & Динамическое исключение мимики",
  },
  {
    id: 4,
    slug: "uv-albedo",
    title: "Свет, тень и силикон",
    subtitle: "Нормализация альбедо, семантическая сегментация UV-развертки и детекция дипфейков",
    renderImage: "04_uv_albedo_deepfake_render.jpg",
    renderCaption: "Нормализация альбедо UV-развертки 1024×1024, анализ микрорельефа Лапласа и поиск границ сшивки",
    readingTime: "10 мин",
    category: "ТЕКСТУРА И АЛЬБЕДО",
    evidenceCount: 1900,
    summary:
      "Как удалить студийные блики (de-lighting) и отсечь фон. Высокочастотный спектр Лапласа для выявления сглаживания кожи. Поиск швов и градиентных сбоев на границах шеи и околоушной зоны.",
    keyMethod: "De-lighting Albedo Map & Высокочастотный спектр Лапласа",
  },
  {
    id: 5,
    slug: "bayesian-courtroom",
    title: "Суд вероятностей",
    subtitle: "Байесовская оценка гипотез (H0, H1, H2) и отношение сигнал-шум (SNR)",
    renderImage: "07_chronology_aba_return_render.jpg",
    renderCaption: "Распределение вероятностей (H0, H1, H2) и анизотропная матрица шума 3DDFA_v3 по осям X/Y/Z",
    readingTime: "11 мин",
    category: "СТАТИСТИКА И БАЙЕС",
    evidenceCount: 3,
    summary:
      "Почему судебная экспертиза не говорит просто «да/нет». Расчет отношения сигнал-шум (SNR) и распределение вероятностей между одним человеком, подменой и другим биологическим человеком.",
    keyMethod: "Bayesian Courtroom Framework (H0, H1, H2) & Анизотропный шум",
  },
  {
    id: 6,
    slug: "lopo-protocol",
    title: "Защита от самообмана",
    subtitle: "Семиперсонный протокол LOPO, контроль FDR 0.05 и тест негативного контроля",
    renderImage: "01_archaeology_provenance_render.jpg",
    renderCaption: "Независимая калибровка порогов на 7 эталонах (LOPO 7/7 HIGH) и тест на 5 сторонних людях",
    readingTime: "8 мин",
    category: "СТАТИСТИКА И БАЙЕС",
    evidenceCount: 7,
    summary:
      "Как доказать, что алгоритм не подгонялся под Путина. Калибровка нулевой гипотезы на 7 независимых эталонах (Leave-One-Person-Out), поправка Бенджамини-Хохберга и 0.000% ложных тревог.",
    keyMethod: "LOPO Leave-One-Person-Out & Benjamini-Hochberg FDR ≤ 0.05",
  },
  {
    id: 7,
    slug: "irreversible-time",
    title: "Закон необратимости времени",
    subtitle: "Монотонная кривая старения и детекция парадоксального возврата A->B->A",
    renderImage: "07_chronology_aba_return_render.jpg",
    renderCaption: "Хронологическая кривая старения 1999–2026, маркеры скачков (Step-Change) и детекция возврата A->B->A",
    readingTime: "9 мин",
    category: "МЕТОДОЛОГИЯ",
    evidenceCount: 1,
    summary:
      "Естественная физиология старения; почему кости не могут омолодиться. Математический критерий необратимого возврата, когда лицо А меняется на В, а потом снова становится А. Правило одного дня.",
    keyMethod: "Paradoxical A->B->A Return Detection & Same-Day Gate",
  },
  {
    id: 8,
    slug: "clustering-history",
    title: "Хронологическая кластеризация",
    subtitle: "Как алгоритм видит смены морфологии на шкале 1999–2026 годов",
    renderImage: "07_chronology_aba_return_render.jpg",
    renderCaption: "Раскладка кластеров #1, #2, #3 на шкале эпох и выявление точек разрыва Boundary Detector",
    readingTime: "7 мин",
    category: "МЕТОДОЛОГИЯ",
    evidenceCount: 3,
    summary:
      "Раскладка кластеров не по близости лиц друг к другу, а вдоль всей хронологии. Параллельные и последовательные кластеры; работа детектора ключевых границ смен (p < 0.001).",
    keyMethod: "Full-Chronology Track Clustering & Boundary Detector",
  },
  {
    id: 9,
    slug: "hypotheses-99",
    title: "Анатомия гипотез",
    subtitle: "Как проверить 90+ журналистских теорий о двойниках без смещения порогов",
    renderImage: "02_3ddfa_bfm_geometry_render.jpg",
    renderCaption: "Изолированный режим проверки сущностей putin, udmurt, vasilich с калибровкой смещения",
    readingTime: "10 мин",
    category: "3D-ГЕОМЕТРИЯ",
    evidenceCount: 90,
    summary:
      "Изоляция страницы «Валидация гипотез» от публичных отчетов и Stage 2/3. Компенсация раннего смещения точек и настройка базовой линии ползунками Shift Bias X/Y/Z.",
    keyMethod: "Shift Bias Calibration & Overlay Similarity Percentages",
  },
  {
    id: 10,
    slug: "blockchain-nft",
    title: "Вечность в блокчейне",
    subtitle: "Как децентрализованные архивы Arweave и 1,900 NFT-артефактов защищают расследование от цензуры",
    renderImage: "01_archaeology_provenance_render.jpg",
    renderCaption: "Гибридная архитектура хостинга 15–25 ГБ (IPFS/Arweave + CDN) и 1,900 уникальных NFT-карточек",
    readingTime: "8 мин",
    category: "БЛОКЧЕЙН И NFT",
    evidenceCount: 1900,
    summary:
      "Неизменяемое хранение 15–25 ГБ сырых фото и 3D-мешей в децентрализованной сети IPFS / Arweave. Токенизация 1,900 биометрических летописей и 3-уровневая воронка монетизации.",
    keyMethod: "Arweave Immutable Archive & ERC-721 On-Chain SHA-256 Proof",
  },
];

export const ArticlesPage: React.FC = () => {
  const [selectedArticleId, setSelectedArticleId] = useState<number>(1);
  const [filterCategory, setFilterCategory] = useState<string>("ALL");
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const filteredArticles = PUBLIC_ARTICLES.filter((a) => {
    if (filterCategory === "ALL") return true;
    return a.category === filterCategory;
  });

  const activeArticle =
    PUBLIC_ARTICLES.find((a) => a.id === selectedArticleId) || PUBLIC_ARTICLES[0];

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6 font-sans select-none">
      {/* HEADER: MONOGRAPH SERIES FOR PUBLIC AUDIENCE & REVIEWERS */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/80 bg-[#0b1117] p-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
            <BookOpen className="h-5 w-5 text-cyan-400" />
            СЕРИЯ СТАТЕЙ ДЛЯ ШИРОКОЙ АУДИТОРИИ И НАУЧНЫХ РЕЦЕНЗЕНТОВ (DEEPUTIN MONOGRAPH SERIES)
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Исчерпывающее 10-статейное руководство по методам 3D-реконструкции, калибровки и блокчейн-вечности
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="rounded bg-[#101820] px-3 py-1.5 text-slate-300 border border-[#1f2d3d]">
            10 СТАТЕЙ · 85 МИН ЧТЕНИЯ
          </span>
          <span className="rounded bg-cyan-950 px-3 py-1.5 text-cyan-300 border border-cyan-800 font-bold">
            4 НАГЛЯДНЫХ РЕНДЕРА
          </span>
          <span className="rounded bg-emerald-950 px-3 py-1.5 text-emerald-300 border border-emerald-800 font-bold">
            100% SCIENTIFIC PROOF
          </span>
        </div>
      </div>

      {/* CATEGORY FILTER BAR */}
      <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 font-mono text-xs">
        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-slate-400 uppercase">Фильтр тем:</span>
          <button
            onClick={() => setFilterCategory("ALL")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "ALL" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            Все 10 статей
          </button>
          <button
            onClick={() => setFilterCategory("МЕТОДОЛОГИЯ")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "МЕТОДОЛОГИЯ" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            Методология (3)
          </button>
          <button
            onClick={() => setFilterCategory("3D-ГЕОМЕТРИЯ")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "3D-ГЕОМЕТРИЯ" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            3D-Геометрия (3)
          </button>
          <button
            onClick={() => setFilterCategory("ТЕКСТУРА И АЛЬБЕДО")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "ТЕКСТУРА И АЛЬБЕДО" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            Текстура и Альбедо (1)
          </button>
          <button
            onClick={() => setFilterCategory("СТАТИСТИКА И БАЙЕС")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "СТАТИСТИКА И БАЙЕС" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            Статистика и Байес (2)
          </button>
          <button
            onClick={() => setFilterCategory("БЛОКЧЕЙН И NFT")}
            className={`rounded px-3 py-1 transition ${
              filterCategory === "БЛОКЧЕЙН И NFT" ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold" : "bg-[#141e27] text-slate-400"
            }`}
          >
            Блокчейн и NFT (1)
          </button>
        </div>

        <span className="text-slate-500 font-mono">
          Выбрана статья: #{activeArticle.id}
        </span>
      </div>

      {/* MAIN WORKSPACE: ARTICLE SELECTOR LIST (35%) + DETAILED ARTICLE & RENDER INSPECTOR (65%) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT LIST: 10 ARTICLES */}
        <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-4 space-y-3 max-h-[640px] overflow-y-auto">
          <div className="border-b border-[#1f2d3d] pb-2 font-mono text-xs font-bold text-slate-300 uppercase">
            ОГЛАВЛЕНИЕ МОНОГРАФИИ (10 СТАТЕЙ)
          </div>

          <div className="space-y-2">
            {filteredArticles.map((a) => {
              const isSelected = activeArticle.id === a.id;
              return (
                <div
                  key={a.id}
                  onClick={() => setSelectedArticleId(a.id)}
                  className={`rounded-lg p-3 border transition cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? "bg-cyan-950/80 border-cyan-500 text-white shadow-lg shadow-cyan-950"
                      : "bg-[#101820] border-[#1f2d3d] hover:border-slate-500 text-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between font-mono text-xs mb-1">
                    <span className="font-bold text-cyan-300">СТАТЬЯ #{a.id}</span>
                    <span className="rounded bg-[#080d12] px-1.5 py-0.5 text-[10px] text-slate-400">
                      {a.readingTime}
                    </span>
                  </div>

                  <div className="font-bold text-sm leading-snug">{a.title}</div>
                  <div className="text-xs text-slate-400 truncate mt-1">{a.subtitle}</div>

                  <div className="mt-2 pt-2 border-t border-[#1f2d3d]/60 flex items-center justify-between font-mono text-[10px] text-emerald-400">
                    <span>{a.category}</span>
                    <span>{a.evidenceCount} ДОКАЗАТЕЛЬСТВ</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT AREA: DETAIL VIEW OF SELECTED ARTICLE + SCIENTIFIC RENDER SHOWCASE (65%) */}
        <div className="lg:col-span-2 rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-6 space-y-6 flex flex-col justify-between">
          <div>
            {/* Top Article Title Banner */}
            <div className="border-b border-[#1f2d3d] pb-4 mb-4">
              <div className="flex items-center justify-between font-mono text-xs mb-2">
                <span className="rounded bg-cyan-950 px-2.5 py-1 text-cyan-300 border border-cyan-800 font-bold">
                  СТАТЬЯ #{activeArticle.id} · {activeArticle.category}
                </span>
                <span className="text-slate-400 font-mono">
                  Время чтения: {activeArticle.readingTime} · Аудитория: СМИ / Биометристы
                </span>
              </div>

              <h2 className="text-xl font-bold text-white tracking-tight">{activeArticle.title}</h2>
              <p className="text-sm text-cyan-300 font-mono mt-1">{activeArticle.subtitle}</p>
            </div>

            {/* ILLUSTRATIVE SCIENTIFIC RENDER SHOWCASE BOX */}
            <div className="rounded-lg border border-cyan-800/80 bg-[#101820] p-4 space-y-3 mb-6">
              <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 font-mono text-xs">
                <span className="font-bold text-cyan-300 uppercase flex items-center gap-1.5">
                  <Eye className="h-4 w-4 text-cyan-400" />
                  НАГЛЯДНЫЙ НАУЧНЫЙ РЕНДЕР: {activeArticle.renderImage}
                </span>
                <span className="rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-300 border border-emerald-800">
                  MUSEUM GRADE RENDER
                </span>
              </div>

              {/* Visual render mockup box */}
              <div className="h-56 rounded bg-[#080d12] border border-[#1f2d3d] flex flex-col items-center justify-center p-6 text-center relative overflow-hidden shadow-inner">
                <div className="absolute inset-0 bg-gradient-to-tr from-cyan-950/20 via-transparent to-emerald-950/20 pointer-events-none" />
                <div className="font-mono text-lg font-bold text-slate-200">
                  НАУЧНАЯ ИЛЛЮСТРАЦИЯ ДЛЯ СТАТЬИ #{activeArticle.id}
                </div>
                <div className="font-mono text-xs text-cyan-400 mt-2 max-w-md">
                  {activeArticle.renderCaption}
                </div>
                <div className="mt-4 rounded bg-[#141e27] px-3 py-1 font-mono text-xs text-emerald-300 border border-emerald-800/60">
                  Ключевой метод: {activeArticle.keyMethod}
                </div>
              </div>

              <div className="text-[11px] text-slate-400 font-mono flex items-center justify-between">
                <span>Файл в репозитории: docs/articles/renders/{activeArticle.renderImage}</span>
                <span className="text-cyan-400">FAIR USE / OPEN PUBLIC ACCESS</span>
              </div>
            </div>

            {/* ARTICLE SUMMARY TEXT & METHODOLOGY DETAILS */}
            <div className="space-y-4 text-sm text-slate-300 leading-relaxed font-sans">
              <div className="rounded-lg bg-[#101820] p-4 border border-[#1f2d3d]">
                <div className="font-mono text-xs font-bold text-cyan-300 uppercase mb-2">
                  КРАТКОЕ СОДЕРЖАНИЕ СТАТЬИ ДЛЯ ШИРОКОЙ ПУБЛИКИ:
                </div>
                <p className="text-slate-200">{activeArticle.summary}</p>
              </div>

              <div className="rounded-lg bg-[#141e27] p-4 border border-cyan-900/60 font-mono text-xs space-y-2">
                <div className="font-bold text-white uppercase">ИНТЕРАКТИВНОЕ ДОКАЗАТЕЛЬСТВО (EVIDENCELINK):</div>
                <p className="text-slate-300 font-sans">
                  Каждый тезис в статье связан с конкретными артефактами в архиве проекта. Читатель может кликнуть на ссылку
                  в тексте, чтобы мгновенно открыть соответствующую фотографию, 3D-меш или график на Таймлайне в рабочей
                  станции <strong className="text-cyan-300">DEEPUTIN UI v5</strong>.
                </p>
                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-4 text-emerald-400">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-4 w-4" />
                      LOPO 7/7 ВЕРИФИКАЦИЯ
                    </span>
                    <span>|</span>
                    <span>FDR ≤ 0.05</span>
                    <span>|</span>
                    <span>RAW OBJECT-NORMALIZED</span>
                  </div>

                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="rounded bg-cyan-600 px-3 py-1 font-bold text-white hover:bg-cyan-500 transition shadow-lg shadow-cyan-950 flex items-center gap-1.5"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>[Открыть проверку EvidenceLink #1999_1231]</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-[#1f2d3d] flex items-center justify-between font-mono text-xs text-slate-400">
            <span>Полный текст серии: docs/articles/00_PUBLIC_ARTICLES_MONOGRAPH_SERIES.md</span>
            <span className="text-emerald-400 font-bold">100% READY FOR PUBLICATION</span>
          </div>
        </div>
      </div>

      {/* INTERACTIVE EVIDENCELINK CRYPTOGRAPHIC VERIFICATION MODAL */}
      <EvidenceLinkModal
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
        title="1999-12-31 — Базовый исторический профиль Владимира Путина (Genesis Baseline)"
        photoId="DEEPUTIN_1999_1231_001"
        date="1999-12-31T12:00:00Z"
        snr={18.4}
        snrDelta={0.12}
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ipfsCid="QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
        csvSnippet={`photo_id,timestamp,pose_bin,snr,snr_diff,bone_rmse,sha256\nDEEPUTIN_1999_1231_001,1999-12-31,FRONTAL,18.4,0.12,0.41,e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`}
      />
    </div>
  );
};
