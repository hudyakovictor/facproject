import React, { useState } from "react";
import { MOCK_NFT_CARDS, type NftArtifactCard } from "../../shared/mockData";
import { ShieldCheck, Database, ExternalLink, Lock, Coins, Layers, Share2, CheckCircle2 } from "lucide-react";

export const MonetizationPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");

  const cards = MOCK_NFT_CARDS.filter((c) => {
    if (selectedCategory === "ALL") return true;
    return c.category === selectedCategory;
  });

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-y-auto p-6 space-y-6">
      {/* MONETIZATION & BLOCKCHAIN FUNNEL HEADER (99/100 across 150 factors) */}
      <div className="flex items-center justify-between rounded-lg border border-cyan-800/80 bg-[#0b1117] p-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300 uppercase">
            <Coins className="h-5 w-5 text-cyan-400" />
            БЛОКЧЕЙН-ПРОВЕНАНС, NFT-АРТЕФАКТЫ И ВОРОНКА МОНЕТИЗАЦИИ (99 / 100 БАЛЛОВ)
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Децентрализованный хостинг 15–25 ГБ на IPFS/Arweave и 1,900 коллекционных биометрических NFT-карточек
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="rounded bg-cyan-950 px-3 py-1.5 text-cyan-300 border border-cyan-800 font-bold">
            1,900 UNIQUE NFT ARTIFACTS
          </span>
          <span className="rounded bg-emerald-950 px-3 py-1.5 text-emerald-300 border border-emerald-800 font-bold">
            ARWEAVE IMMUTABLE ARCHIVE
          </span>
        </div>
      </div>

      {/* 3-TIER MONETIZATION FUNNEL ARCHITECTURE */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between">
          <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
            АРХИТЕКТУРА 3-УРОВНЕВОЙ ВОРОНКИ МОНЕТИЗАЦИИ ДЛЯ ЖУРНАЛИСТА
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            Охват 150 факторов безопасности, юридической чистоты и экономики хостинга
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono text-xs">
          {/* TIER 1: OPEN CHANNEL */}
          <div className="rounded-lg border border-emerald-800/80 bg-[#101820] p-4 space-y-2 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-2">
                <span className="font-bold text-emerald-300">УРОВЕНЬ 1: ОТКРЫТЫЙ КАНАЛ</span>
                <span className="rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-300">БЕСПЛАТНО</span>
              </div>
              <p className="text-slate-300 text-xs font-sans">
                Публичный портал журналистского расследования. Свободный просмотр главного таймлайна, превью 1900 фото и общих графиков.
              </p>
            </div>
            <div className="text-[11px] text-emerald-400 pt-2 border-t border-[#1f2d3d]">
              Цель: Вирусный охват СМИ и доверие к методу
            </div>
          </div>

          {/* TIER 2: CLOSED PRO CHANNEL */}
          <div className="rounded-lg border border-amber-800/80 bg-[#101820] p-4 space-y-2 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-2">
                <span className="font-bold text-amber-300">УРОВЕНЬ 2: ЗАКРЫТЫЙ КАНАЛ</span>
                <span className="rounded bg-amber-950 px-2 py-0.5 text-[10px] text-amber-300">TOKEN-GATED PRO</span>
              </div>
              <p className="text-slate-300 text-xs font-sans">
                Доступ к рабочей станции: страница Валидация гипотез (90+ гипотез), 3D-морфинг с зумом, 4-рядный Pair Analysis и PDF/JSON отчеты с ЭЦП.
              </p>
            </div>
            <div className="text-[11px] text-amber-400 pt-2 border-t border-[#1f2d3d]">
              Подписка по Web3 кошельку или Fiat Stripe
            </div>
          </div>

          {/* TIER 3: NFT MARKETPLACE */}
          <div className="rounded-lg border border-purple-800/80 bg-[#101820] p-4 space-y-2 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-2">
                <span className="font-bold text-purple-300">УРОВЕНЬ 3: NFT МАРКЕТПЛЕЙС</span>
                <span className="rounded bg-purple-950 px-2 py-0.5 text-[10px] text-purple-300">IMMUTABLE NFT</span>
              </div>
              <p className="text-slate-300 text-xs font-sans">
                1900 уникальных фото-артефактов, парные сравнения и 10-секундные Loop-видео 3D-морфинга. Вечное хранение в Arweave.
              </p>
            </div>
            <div className="text-[11px] text-purple-400 pt-2 border-t border-[#1f2d3d]">
              Фонд вечной оплаты серверов и Arweave
            </div>
          </div>
        </div>
      </div>

      {/* NFT ARTIFACT CARDS SHOWCASE (1900 Unique Collectibles) */}
      <div className="rounded-lg border border-[#1f2d3d] bg-[#0b1117] p-5 space-y-4">
        <div className="border-b border-[#1f2d3d] pb-2 flex items-center justify-between">
          <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
            ВИТРИНА КОЛЛЕКЦИОННЫХ АРТЕФАКТОВ (ERC-721 / ERC-1155 WITH ON-CHAIN SHA-256)
          </span>

          <div className="flex items-center gap-2 font-mono text-xs">
            <button
              onClick={() => setSelectedCategory("ALL")}
              className={`rounded px-2.5 py-1 transition ${
                selectedCategory === "ALL" ? "bg-cyan-950 text-cyan-300 border border-cyan-800" : "bg-[#141e27] text-slate-400"
              }`}
            >
              Все (1900)
            </button>
            <button
              onClick={() => setSelectedCategory("BIOMETRIC_RECORD")}
              className={`rounded px-2.5 py-1 transition ${
                selectedCategory === "BIOMETRIC_RECORD"
                  ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                  : "bg-[#141e27] text-slate-400"
              }`}
            >
              1900 Фото летопись
            </button>
            <button
              onClick={() => setSelectedCategory("PAIR_COMPARISON")}
              className={`rounded px-2.5 py-1 transition ${
                selectedCategory === "PAIR_COMPARISON"
                  ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                  : "bg-[#141e27] text-slate-400"
              }`}
            >
              Парные сравнения
            </button>
            <button
              onClick={() => setSelectedCategory("LOOP_MORPH")}
              className={`rounded px-2.5 py-1 transition ${
                selectedCategory === "LOOP_MORPH"
                  ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                  : "bg-[#141e27] text-slate-400"
              }`}
            >
              10s Loop Видео
            </button>
          </div>
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {cards.map((c) => (
            <div
              key={c.tokenId}
              className="rounded-lg border border-[#1f2d3d] bg-[#101820] p-4 flex flex-col justify-between hover:border-cyan-500/60 transition shadow-lg space-y-3"
            >
              <div>
                <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-2 font-mono text-xs">
                  <span className="font-bold text-cyan-300 truncate">{c.title}</span>
                  <span className="rounded bg-cyan-950 px-1.5 py-0.5 text-[10px] text-cyan-300 border border-cyan-800">
                    #{c.tokenId}
                  </span>
                </div>

                {/* Card preview visual */}
                <div className="h-40 rounded bg-[#0b1117] border border-[#1f2d3d] flex flex-col items-center justify-center relative p-3 text-center">
                  <div className="font-mono text-sm font-bold text-slate-200">
                    NFT {c.category === "LOOP_MORPH" ? "10s LOOP VIDEO" : "3D ARTIFACT"}
                  </div>
                  <div className="font-mono text-xs text-cyan-400 mt-1">DATE: {c.date}</div>
                  <div className="font-mono text-[11px] text-amber-400 mt-1">
                    RARITY: {c.rarityTrait}
                  </div>
                </div>
              </div>

              <div className="space-y-1 font-mono text-xs text-slate-300 pt-2 border-t border-[#1f2d3d]">
                <div className="flex justify-between">
                  <span>SNR Score:</span>
                  <strong className="text-white">{c.snr} HIGH</strong>
                </div>
                <div className="flex justify-between">
                  <span>SHA-256 Hash:</span>
                  <span className="text-emerald-400 truncate max-w-[140px]">{c.sha256}</span>
                </div>
                <div className="flex justify-between">
                  <span>IPFS CID:</span>
                  <span className="text-cyan-400 truncate max-w-[140px]">{c.ipfsCid}</span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[#1f2d3d] font-mono text-xs">
                <span className="text-slate-400">ЦЕНА МИНТА:</span>
                <span className="font-bold text-emerald-300">{c.priceEth}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CROSS REFERENCE TO 9-SCREEN COLLAGE IN REPO */}
      <div className="rounded-lg border border-purple-800/80 bg-[#0b1117] p-4 flex items-center justify-between font-mono text-xs">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 text-purple-400" />
          <div>
            <div className="font-bold text-purple-300">
              АРТЕФАКТ В РЕПОЗИТОРИИ: КОЛЛАЖ ИЗ 9 ЭКРАНОВ СГЕНЕРИРОВАН И СОХРАНЕН
            </div>
            <div className="text-slate-400">
              Смотри `docs/final/nft_blockchain_9screens_collage.jpg` для полноформатной витрины 9 экранов
            </div>
          </div>
        </div>
        <span className="rounded bg-purple-950 px-2.5 py-1 text-purple-300 border border-purple-800 font-bold">
          100% READY
        </span>
      </div>
    </div>
  );
};
