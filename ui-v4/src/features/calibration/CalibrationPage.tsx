/**
 * Calibration Workspace (Iteration 10).
 *
 * Dashboard over the calibration dataset: 7 persons × 9 pose bins coverage,
 * frame and same-person pair counts, and the calibrated thresholds of the
 * active Stage 2 run (LDM106 / LDM134 per pose bin) with the explicit
 * diagnostic-vs-calibrated distinction. Read-only.
 */
import { useEffect, useState } from "react";
import {
  calibrationThresholds, calibrationWorkspace,
  type CalibrationThresholdRow, type CalibrationThresholds, type CalibrationWorkspace,
} from "../../shared/api";
import { LABEL, POSES, type Pose } from "../../shared/types";
import { logError } from "../../shared/logger";

export default function CalibrationPage() {
  const [workspace, setWorkspace] = useState<CalibrationWorkspace | null>(null);
  const [thresholds, setThresholds] = useState<CalibrationThresholds | null>(null);
  const [message, setMessage] = useState("");
  const [activeBin, setActiveBin] = useState<string>("frontal");

  useEffect(() => {
    void Promise.all([calibrationWorkspace(), calibrationThresholds()])
      .then(([ws, th]) => { setWorkspace(ws); setThresholds(th); })
      .catch(error => { const text = error instanceof Error ? error.message : String(error); setMessage(text); logError("calibration", "не удалось загрузить калибровку", error); });
  }, []);

  const reference = (rows: CalibrationThresholdRow[] | undefined, pose: string, count: 106 | 134) =>
    rows?.find(row => row.pose_bin === pose && row.count === count) || null;

  const binThresholds = thresholds?.references ?? [];
  const active106 = reference(binThresholds, activeBin, 106);
  const active134 = reference(binThresholds, activeBin, 134);

  return (
    <div className="page-shell calibration-page">
      <div className="page-heading">
        <div>
          <small>ITERATION 10 · CALIBRATION WORKSPACE</small>
          <h1>Калибровка · 7 персон × 9 ракурсов</h1>
          <p>Покрытие калибровочного датасета и откалиброванные same-person шумы активного Stage 2 run.</p>
        </div>
        {thresholds && (
          <span className={`live ${thresholds.calibrated ? "research" : "error"}`}>
            {thresholds.calibrated ? `● CALIBRATED · run ${thresholds.run_id}` : "● diagnostic-only — запустите Stage 2"}
          </span>
        )}
      </div>
      {message && <div className="notice wide">{message}</div>}

      {workspace?.status === "ready" && (
        <>
          <section className="card">
            <header><span>01</span><div><b>Покрытие персон × ракурсов</b><small>{workspace.total_frames} кадров · {workspace.covered_bin_count}/9 полных бинов · оценка same-person пар: {workspace.total_pair_estimate}</small></div></header>
            <div className="cal-matrix">
              <table>
                <thead>
                  <tr><th>person</th>{POSES.map(pose => <th key={pose}>{LABEL[pose].replace("Левый", "L").replace("Правый", "R").replace("Фронтальный", "F")}</th>)}<th>Σ</th></tr>
                </thead>
                <tbody>
                  {workspace.persons?.map(person => (
                    <tr key={person.person}>
                      <td><b>{person.person}</b></td>
                      {POSES.map(pose => (
                        <td key={pose} className={person.per_bin[pose] > 1 ? "filled" : person.per_bin[pose] > 0 ? "partial" : "empty"}>
                          {person.per_bin[pose] || "·"}
                        </td>
                      ))}
                      <td><b>{person.total}</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="cal-legend">
              <span><i className="filled" /> ≥2 кадра (пары возможны)</span>
              <span><i className="partial" /> 1 кадр</span>
              <span><i className="empty" /> нет кадров</span>
            </div>
          </section>

          <section className="card">
            <header><span>02</span><div><b>Same-person пары по бинам</b><small>оценка соседних пар внутри каждого бина</small></div></header>
            <div className="cal-bin-grid">
              {workspace.pose_bins?.map(bin => (
                <button key={bin.pose} className={activeBin === bin.pose ? "active" : ""} onClick={() => setActiveBin(bin.pose)}>
                  <b>{LABEL[bin.pose as Pose]}</b>
                  <span>{bin.total} кадров · {bin.persons_with_frames}/7 персон</span>
                  <em>{bin.adjacent_pair_estimate} пар</em>
                </button>
              ))}
            </div>
          </section>

          <section className="card">
            <header><span>03</span><div><b>Откалиброванные пороги · {LABEL[activeBin as Pose]}</b><small>median / MAD / p95 per-point same-person noise</small></div></header>
            {thresholds?.calibrated ? (
              <div className="cal-thresholds">
                {[active106, active134].filter(Boolean).map(ref => (
                  <div key={`${ref!.pose_bin}-${ref!.count}`} className="cal-threshold-card">
                    <h4>LDM {ref!.count}</h4>
                    <div className="cal-threshold-values">
                      <div><span>median</span><b>{ref!.scalar.median?.toFixed(5) ?? "—"}</b></div>
                      <div><span>MAD</span><b>{ref!.scalar.mad?.toFixed(5) ?? "—"}</b></div>
                      <div><span>p95</span><b>{ref!.scalar.p95?.toFixed(5) ?? "—"}</b></div>
                      <div><span>точек с данными</span><b>{ref!.supported_points ?? "—"}</b></div>
                    </div>
                  </div>
                ))}
                {!active106 && !active134 && <em>Для этого бина нет откалиброванных референсов.</em>}
                <div className="cal-threshold-note">
                  <b>Диагностический vs откалиброванный порог</b>
                  <p>Ползунки в Landmark Comparison — <b>диагностические</b> (референс эксперта). Значения выше — это p95 распределения
                  same-person шума из 7 калибровочных наборов (LOPO-валидированного). Ни одно из них не является вердиктом.</p>
                  {thresholds.sensitivity && (
                    <details>
                      <summary>LOPO / leave-one-dataset-out sensitivity</summary>
                      <pre>{JSON.stringify(thresholds.sensitivity, null, 1).slice(0, 3000)}</pre>
                    </details>
                  )}
                </div>
              </div>
            ) : (
              <div className="state error"><span>!</span><b>Stage 2 ещё не запускался</b><p>{thresholds?.detail}</p></div>
            )}
          </section>
        </>
      )}
      {workspace?.status !== "ready" && (
        <div className="state error"><span>!</span><b>Калибровочный индекс недоступен</b><p>{workspace?.detail}</p></div>
      )}
    </div>
  );
}
