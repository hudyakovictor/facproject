import { useState } from "react";
import { Outlet } from "@tanstack/react-router";
import { useTimeline } from "../shared/api/queries";
import { TopBar } from "../features/shell/TopBar";
import { ConsoleLogDrawer } from "../features/shell/ConsoleLogDrawer";
import { NotAVerdictBar } from "../shared/ui/NotAVerdictBar";
import { countFindings } from "../shared/findings";
import { resolveStage, stageLabel } from "../shared/stage";

export default function RootLayout() {
  /**
   * Идентификатор бина в каноническом нижнем регистре справочника
   * `shared/poseBins`. Раньше здесь было "FRONTAL", и совпадение с данными
   * держалось только на `toLowerCase()` внутри отдельных страниц.
   */
  const [activePose, setActivePose] = useState<string>("frontal");
  const [qualityThreshold, setQualityThreshold] = useState<number>(0);
  const [mouthThreshold, setMouthThreshold] = useState<number>(0.35);
  const [poseAngleThreshold, setPoseAngleThreshold] = useState<number>(6);

  const timeline = useTimeline();
  const photos = timeline.data?.photos ?? [];
  const stage = resolveStage(timeline.data);

  return (
    <div className="min-h-screen w-full bg-[#080d12] text-[#e2e8f0] font-sans antialiased flex flex-col pb-9">
      <TopBar
        activePose={activePose}
        onPoseChange={setActivePose}
        qualityThreshold={qualityThreshold}
        onQualityThresholdChange={setQualityThreshold}
        mouthThreshold={mouthThreshold}
        onMouthThresholdChange={setMouthThreshold}
        poseAngleThreshold={poseAngleThreshold}
        onPoseAngleThresholdChange={setPoseAngleThreshold}
      />
      <main className="flex-1 flex flex-col w-full">
        <Outlet />
      </main>
      {/*
        Правило 20 AGENTS.md: маркировка «не вердикт» видна постоянно, на каждом
        экране, а не только там, где о ней вспомнили.
      */}
      <NotAVerdictBar
        sourceMode={timeline.data?.source_mode}
        stageLabel={stageLabel(stage)}
        findingCount={photos.length ? countFindings(photos) : undefined}
      />
      <ConsoleLogDrawer />
    </div>
  );
}
