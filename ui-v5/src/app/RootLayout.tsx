import React, { useState } from "react";
import { Outlet } from "@tanstack/react-router";
import { TopBar } from "../features/shell/TopBar";
import { ConsoleLogDrawer } from "../features/shell/ConsoleLogDrawer";

export default function RootLayout() {
  const [activePose, setActivePose] = useState<string>("FRONTAL");
  const [qualityThreshold, setQualityThreshold] = useState<number>(0);
  const [mouthThreshold, setMouthThreshold] = useState<number>(0.35);
  const [poseAngleThreshold, setPoseAngleThreshold] = useState<number>(6);

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
      <ConsoleLogDrawer />
    </div>
  );
}
