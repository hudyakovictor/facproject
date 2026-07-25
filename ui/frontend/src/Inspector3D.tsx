import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
// @ts-ignore
import gifshot from "gifshot";
import { getMeshPreview, getPairComparison } from "./api";
import { uiLog } from "./logStore";

export function Inspector3D({ recordId, recordBId }: { recordId: string; recordBId?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState<any>(null);
  const [mode, setMode] = useState<"single" | "pair" | "morph">("single");
  const [morphAlpha, setMorphAlpha] = useState(0.5);
  const [animating, setAnimating] = useState(false);
  const [exportingGif, setExportingGif] = useState(false);
  const [gifProgress, setGifProgress] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    const p = recordBId && (mode === "pair" || mode === "morph") ? getPairComparison(recordId, recordBId) : getMeshPreview(recordId);
    p.then((res) => {
      if (cancelled) return;
      setData(res);
      setLoading(false);
      uiLog("info", "inspector3d", `Загружена 3D сцена для ${recordId}${recordBId ? ` и ${recordBId}` : ""} (режим: ${mode})`);
    }).catch((e) => {
      if (cancelled) return;
      setError(String(e));
      setLoading(false);
      uiLog("error", "inspector3d", String(e));
    });
    return () => { cancelled = true; };
  }, [recordId, recordBId, mode]);

  // Handle continuous morph animation loop
  useEffect(() => {
    if (!animating || mode !== "morph") return;
    let timer: any;
    let forward = true;
    function step() {
      setMorphAlpha((prev) => {
        let next = forward ? prev + 0.02 : prev - 0.02;
        if (next >= 1) { next = 1; forward = false; }
        if (next <= 0) { next = 0; forward = true; }
        return next;
      });
      timer = setTimeout(step, 40);
    }
    step();
    return () => clearTimeout(timer);
  }, [animating, mode]);

  // Three.js rendering effect
  useEffect(() => {
    if (!containerRef.current || !data) return;
    const container = containerRef.current;
    container.innerHTML = "";

    const width = container.clientWidth || 400;
    const height = container.clientHeight || 400;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e1116);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 3.5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
    directionalLight.position.set(2, 4, 3);
    scene.add(directionalLight);

    const group = new THREE.Group();
    scene.add(group);

    if (mode === "single" || !recordBId) {
      const vertices: number[][] = data.vertices || [];
      if (vertices.length > 0) {
        const geom = new THREE.BufferGeometry();
        const pos = new Float32Array(vertices.length * 3);
        for (let i = 0; i < vertices.length; i++) {
          pos[i * 3] = vertices[i][0] || 0;
          pos[i * 3 + 1] = vertices[i][1] || 0;
          pos[i * 3 + 2] = vertices[i][2] || 0;
        }
        geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        geom.center();
        const mat = new THREE.PointsMaterial({ color: 0x3b82f6, size: 0.018 });
        group.add(new THREE.Points(geom, mat));
      }
    } else if (mode === "pair") {
      const ldmA: number[][] = data.landmarks_a || [];
      const distances: number[] = data.landmark_distances || [];
      const maxDist = data.max_distance || 0.1;

      if (ldmA.length > 0) {
        const ldmGeom = new THREE.BufferGeometry();
        const ldmPos = new Float32Array(ldmA.length * 3);
        const ldmColors = new Float32Array(ldmA.length * 3);
        const colorGreen = new THREE.Color(0x52c89a);
        const colorYellow = new THREE.Color(0xf5c66f);
        const colorRed = new THREE.Color(0xef7373);

        for (let i = 0; i < ldmA.length; i++) {
          ldmPos[i * 3] = ldmA[i][0] || 0;
          ldmPos[i * 3 + 1] = ldmA[i][1] || 0;
          ldmPos[i * 3 + 2] = ldmA[i][2] || 0;

          const ratio = maxDist > 0 ? Math.min(1, (distances[i] || 0) / maxDist) : 0;
          let c = ratio > 0.5 ? colorYellow.clone().lerp(colorRed, (ratio - 0.5) * 2) : colorGreen.clone().lerp(colorYellow, ratio * 2);
          ldmColors[i * 3] = c.r; ldmColors[i * 3 + 1] = c.g; ldmColors[i * 3 + 2] = c.b;
        }

        ldmGeom.setAttribute("position", new THREE.BufferAttribute(ldmPos, 3));
        ldmGeom.setAttribute("color", new THREE.BufferAttribute(ldmColors, 3));
        ldmGeom.center();
        group.add(new THREE.Points(ldmGeom, new THREE.PointsMaterial({ size: 0.05, vertexColors: true })));
      }
    } else if (mode === "morph") {
      // Morphing mode between mesh A and mesh B using morphAlpha
      const meshA: number[][] = data.mesh_a || [];
      const meshB: number[][] = data.mesh_b || [];
      const count = Math.min(meshA.length, meshB.length);

      if (count > 0) {
        const geom = new THREE.BufferGeometry();
        const pos = new Float32Array(count * 3);
        const alpha = morphAlpha;

        for (let i = 0; i < count; i++) {
          const ax = meshA[i][0] || 0, ay = meshA[i][1] || 0, az = meshA[i][2] || 0;
          const bx = meshB[i][0] || 0, by = meshB[i][1] || 0, bz = meshB[i][2] || 0;
          pos[i * 3] = ax * (1 - alpha) + bx * alpha;
          pos[i * 3 + 1] = ay * (1 - alpha) + by * alpha;
          pos[i * 3 + 2] = az * (1 - alpha) + bz * alpha;
        }

        geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        geom.center();
        const mat = new THREE.PointsMaterial({ color: 0x60a5fa, size: 0.02 });
        group.add(new THREE.Points(geom, mat));
      }
    }

    let frameId = 0;
    function animate() {
      frameId = requestAnimationFrame(animate);
      group.rotation.y += 0.005;
      renderer.render(scene, camera);
    }
    animate();

    function handleResize() {
      if (!container) return;
      const w = container.clientWidth || 400;
      const h = container.clientHeight || 400;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      container.innerHTML = "";
    };
  }, [data, mode, morphAlpha, recordBId]);

  // Function to capture and create looping GIF of morphing sequence
  function exportLoopingGif() {
    if (!containerRef.current || exportingGif) return;
    setExportingGif(true);
    setGifProgress(10);
    uiLog("info", "inspector3d", "Начало генерации гиф-анимации морфинга…");

    const images: string[] = [];
    const steps = 15;
    let currentStep = 0;

    function captureStep() {
      if (currentStep <= steps) {
        const alpha = currentStep / steps;
        setMorphAlpha(alpha);
        setGifProgress(10 + Math.round((currentStep / steps) * 60));
        setTimeout(() => {
          const canvas = containerRef.current?.querySelector("canvas");
          if (canvas) {
            images.push(canvas.toDataURL("image/png"));
          }
          currentStep++;
          captureStep();
        }, 120);
      } else {
        setGifProgress(80);
        gifshot.createGIF({
          images: images,
          interval: 0.1,
          numFrames: steps,
          gifWidth: 320,
          gifHeight: 320,
        }, (obj: any) => {
          setExportingGif(false);
          setGifProgress(100);
          if (!obj.error) {
            const wind = window.open();
            wind?.document.write(`<img src="${obj.image}" alt="Morphing GIF"/><h3>Зацикленная гиф-анимация морфинга создана</h3>`);
            uiLog("info", "inspector3d", "Гиф-анимация успешно создана и открыта в новой вкладке");
          } else {
            uiLog("error", "inspector3d", `Ошибка создания GIF: ${obj.errorCode}`);
          }
        });
      }
    }
    captureStep();
  }

  return <div className="inspector-3d-container">
    <div className="inspector-3d-header">
      <b>3D Inspector · Morphing & Divergence</b>
      <div className="inspector-3d-modes">
        <button className={mode === "single" ? "active" : ""} onClick={() => setMode("single")}>Одиночный меш</button>
        {recordBId && <>
          <button className={mode === "pair" ? "active" : ""} onClick={() => setMode("pair")}>Тепловая карта точек</button>
          <button className={mode === "morph" ? "active" : ""} onClick={() => setMode("morph")}>Морфинг мешей</button>
        </>}
      </div>
    </div>
    {mode === "morph" && recordBId && <div className="morph-toolbar">
      <span>Морфинг (α = {morphAlpha.toFixed(2)})</span>
      <input type="range" min="0" max="1" step="0.01" value={morphAlpha} onChange={(e) => setMorphAlpha(parseFloat(e.target.value))} />
      <button onClick={() => setAnimating((x) => !x)}>{animating ? "Стоп" : "Авто-петля"}</button>
      <button disabled={exportingGif} onClick={exportingGif ? undefined : exportLoopingGif}>
        {exportingGif ? `Экспорт GIF (${gifProgress}%)...` : "Сохранить GIF"}
      </button>
    </div>}
    <div className="inspector-3d-viewport" ref={containerRef}>
      {loading && <div className="inspector-3d-status">Загрузка 3D сцены…</div>}
      {error && <div className="inspector-3d-status error">{error}</div>}
      {!loading && !error && data?.status === "synthetic_fallback" && <div className="inspector-3d-badge">Демонстрационное облако точек (кеш не найден)</div>}
    </div>
    <div className="inspector-3d-footer">
      <small>{mode === "morph" ? "Интерактивный слайдер смешивания геометрии 3D моделей" : "Вращение сцены автоматически · Ландмарки LDM106"}</small>
    </div>
  </div>;
}
