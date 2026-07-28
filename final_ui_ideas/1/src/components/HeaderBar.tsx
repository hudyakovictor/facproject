/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Lock, Unlock, Download, EyeOff, Sun, Moon, ZoomIn, ZoomOut, Maximize2, ShieldAlert } from 'lucide-react';
import { PoseBucket } from '../types';

interface HeaderBarProps {
  currentDataset: 'main' | 'calibration';
  setDataset: (ds: 'main' | 'calibration') => void;
  currentBucket: PoseBucket | 'all';
  setBucket: (bucket: PoseBucket | 'all') => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  isLocked: boolean;
  setIsLocked: (l: boolean) => void;
  zoomLevel: number; // 20 - 400
  setZoomLevel: (z: number) => void;
  darkMode: boolean;
  setDarkMode: (dm: boolean) => void;
  onExport: () => void;
  onBulkHide: () => void;
  showAnomaliesOnly: boolean;
  setShowAnomaliesOnly: (b: boolean) => void;
  qualityThreshold: number;
  setQualityThreshold: (val: number) => void;
}

export default function HeaderBar({
  currentDataset,
  setDataset,
  currentBucket,
  setBucket,
  searchQuery,
  setSearchQuery,
  isLocked,
  setIsLocked,
  zoomLevel,
  setZoomLevel,
  darkMode,
  setDarkMode,
  onExport,
  onBulkHide,
  showAnomaliesOnly,
  setShowAnomaliesOnly,
  qualityThreshold,
  setQualityThreshold
}: HeaderBarProps) {
  return (
    <header className="h-[52px] border-b border-white/10 bg-[#0d0d0f] px-4 flex items-center justify-between z-30 select-none">
      {/* LEFT: Branding and Watermarks */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <div className="bg-[#dd6974]/20 px-2 py-0.5 border border-[#dd6974]/40 rounded-sm">
            <span className="font-display font-medium text-xs tracking-widest text-[#dd6974]">DEEPUTIN</span>
          </div>
          <span className="text-[10px] font-mono text-white/40 border-l border-white/15 pl-2 select-none">
            БИОМЕТРИЯ v2.1.0 · СОСТОЯНИЕ СИСТЕМЫ: АКТИВНО
          </span>
        </div>

        <div className="hidden lg:flex items-center space-x-3 text-[10px] font-mono text-white/60 bg-white/5 px-2.5 py-1 rounded border border-white/5">
          <span className="text-[#4f98a3] font-semibold">АРТЕФАКТ v2.1.0</span>
          <span>•</span>
          <span>ОБНАРУЖЕНО 1,809 СНИМКОВ</span>
          <span>•</span>
          <span className="text-[#e8af34]">ПОСЛЕДНИЙ ЗАПУСК: 2026-06-04</span>
        </div>

        {/* Dataset lock toggle */}
        <button
          onClick={() => setIsLocked(!isLocked)}
          className={`p-1.5 rounded transition hover:bg-white/5 cursor-pointer text-xs flex items-center gap-1 ${
            isLocked ? 'text-white/60' : 'text-[#e8af34]'
          }`}
          title={isLocked ? 'Датасет защищен от редактирования' : 'Редактирование включено'}
        >
          {isLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
          <span className="hidden xl:inline text-[9px] font-mono">{isLocked ? 'БЛОКИРОВКА' : 'РЕДАКТОР'}</span>
        </button>
      </div>

      {/* CENTER: Filtering & Data Search Controls */}
      <div className="flex items-center space-x-3 max-w-[50%]">
        {/* Dataset toggler */}
        <div className="flex items-center bg-[#13131a] border border-white/15 p-0.5 rounded text-[10px] font-mono">
          <button
            onClick={() => setDataset('main')}
            className={`px-2.5 py-0.5 rounded transition cursor-pointer ${
              currentDataset === 'main'
                ? 'bg-[#4f98a3] text-black font-semibold'
                : 'text-white/60 hover:text-white'
            }`}
          >
            БАЗА
          </button>
          <button
            onClick={() => setDataset('calibration')}
            className={`px-2.5 py-0.5 rounded transition cursor-pointer ${
              currentDataset === 'calibration'
                ? 'bg-[#4f98a3] text-black font-semibold'
                : 'text-white/60 hover:text-white'
            }`}
          >
            КАЛИБРОВКА
          </button>
        </div>

        {/* Bucket filter */}
        <select
          value={currentBucket}
          aria-label="Pose Bucket Filter"
          onChange={(e) => setBucket(e.target.value as PoseBucket | 'all')}
          className="bg-[#13131a] text-white/80 border border-white/15 px-2 py-1 rounded text-[10px] font-mono outline-none cursor-pointer hover:border-white/30"
        >
          <option value="all">ВСЕ РАКУРСЫ</option>
          <option value="frontal_0">Фронтальный (0°)</option>
          <option value="frontal_yaw15">Поворот 15°</option>
          <option value="frontal_yaw30">Поворот 30°</option>
          <option value="profile_L">Профиль влево</option>
          <option value="profile_R">Профиль вправо</option>
        </select>

        {/* Search Input */}
        <div className="relative">
          <input
            type="text"
            placeholder="Поиск по ID или году..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-[180px] xl:w-[240px] bg-[#1a1a24] text-white placeholder-white/30 border border-white/10 px-2.5 py-1 pl-3 rounded text-[11px] font-mono focus:outline-none focus:border-[#4f98a3] transition"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1.5 text-white/40 hover:text-white text-[10px] font-mono"
            >
              СБРОС
            </button>
          )}
        </div>
      </div>

      {/* RIGHT: Actions and Visual Utilities */}
      <div className="flex items-center space-x-3">
        {/* Toggle Anomalies */}
        <button
          onClick={() => setShowAnomaliesOnly(!showAnomaliesOnly)}
          className={`px-2.5 py-1 rounded border text-[10px] font-mono transition cursor-pointer ${
            showAnomaliesOnly
              ? 'bg-[#dd6974]/20 border-[#dd6974] text-[#dd6974] font-semibold'
              : 'border-white/10 text-white/50 hover:border-white/20'
          }`}
        >
          ⚠️ Только аномалии
        </button>

        {/* Quality limit */}
        <div className="hidden xl:flex items-center gap-1.5 text-[9px] font-mono bg-white/5 border border-white/5 px-2 py-1 rounded">
          <span className="text-white/40">КАЧЕСТВО &gt;</span>
          <input
            type="range"
            min="0.0"
            max="0.80"
            step="0.05"
            aria-label="Quality score threshold"
            value={qualityThreshold}
            onChange={(e) => setQualityThreshold(parseFloat(e.target.value))}
            className="w-16 accent-[#6daa45] h-1 bg-white/10 rounded-lg cursor-pointer"
          />
          <span className="text-[#6daa45]">{qualityThreshold.toFixed(2)}</span>
        </div>

        {/* Hide selected trigger */}
        <button
          onClick={onBulkHide}
          className="p-1 px-2 border border-white/10 rounded text-white/60 hover:text-[#dd6974] hover:bg-[#dd6974]/5 transition cursor-pointer flex items-center gap-1.5"
          title="Скрыть сомнительные/заблюренные кадры"
        >
          <EyeOff className="w-3.5 h-3.5" />
          <span className="hidden xl:inline text-[9px] font-mono">СКРЫТЬ ПЛОХИЕ</span>
        </button>

        {/* Export triggers */}
        <button
          onClick={onExport}
          className="px-2.5 py-1 bg-[#6daa45]/15 border border-[#6daa45]/30 text-[#6daa45] hover:bg-[#6daa45]/25 rounded text-[10px] font-mono transition cursor-pointer flex items-center gap-1"
        >
          <Download className="w-3.5 h-3.5" />
          <span>ОТЧЕТ JSON</span>
        </button>

        {/* Dark/Light mode toggle */}
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-1.5 text-white/40 hover:text-white hover:bg-white/5 rounded cursor-pointer transition"
          title="Сменить тему оформления"
        >
          {darkMode ? <Sun className="w-4 h-4 text-[#e8af34]" /> : <Moon className="w-4 h-4 text-white" />}
        </button>

        {/* Timeline Zoom control */}
        <div className="flex items-center bg-[#13131a] border border-white/10 rounded-sm p-0.5 text-[10px] font-mono">
          <button
            onClick={() => setZoomLevel(Math.max(20, zoomLevel - 20))}
            className="p-1 hover:bg-white/5 text-white/70 hover:text-white"
            title="Отдалить временную шкалу"
          >
            <ZoomOut className="w-3 h-3" />
          </button>
          <span className="w-9 text-center text-[9px] text-[#4f98a3] select-none">{zoomLevel}%</span>
          <button
            onClick={() => setZoomLevel(Math.min(400, zoomLevel + 20))}
            className="p-1 hover:bg-white/5 text-white/70 hover:text-white"
            title="Приблизить временную шкалу"
          >
            <ZoomIn className="w-3 h-3" />
          </button>
          <button
            onClick={() => setZoomLevel(100)}
            className="p-1 hover:bg-[#4f98a3]/20 text-[#4f98a3] border-l border-white/10 pl-1.5 pr-1"
            title="Вписать по размеру"
          >
            <Maximize2 className="w-3 h-3" />
          </button>
        </div>
      </div>
    </header>
  );
}
