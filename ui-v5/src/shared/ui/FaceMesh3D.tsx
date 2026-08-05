import React, { useEffect, useRef, useState } from "react";

export type RenderMode = "3d-wireframe" | "3d-solid" | "uv-texture" | "heatmap";

interface FaceMesh3DProps {
  mode: RenderMode;
  showKeypoints?: boolean;
  year?: number;
  snrScore?: number;
  interactive?: boolean;
  className?: string;
}

interface Vertex3D {
  x: number;
  y: number;
  z: number;
  isLandmark?: boolean;
  zone?: "nose" | "orbital" | "zygomatic" | "jaw" | "forehead" | "skin";
}

interface FaceData {
  vertices: Vertex3D[];
  edges: [number, number][];
}

// Generate an anatomical 3D face mesh structure (BFM simplified topology)
function generateAnatomicalFaceMesh(): FaceData {
  const vertices: Vertex3D[] = [];
  const edges: [number, number][] = [];

  // Generate symmetrical face contour, eyes, nose, zygomatic arch, jaw, lips, forehead
  const rows = 11;
  const cols = 9;

  for (let r = 0; r < rows; r++) {
    const v = r / (rows - 1); // 0 (top forehead) to 1 (chin)
    const y = (0.5 - v) * 2.2; // +1.1 to -1.1

    for (let c = 0; c < cols; c++) {
      const u = c / (cols - 1); // 0 (left) to 1 (right)
      const x = (u - 0.5) * 1.6; // -0.8 to +0.8

      // Ellipsoid face curvature + anatomical relief
      const distFromCenter = Math.sqrt(x * x + y * y * 0.4);
      let z = Math.max(0, Math.sqrt(Math.max(0, 1.2 - distFromCenter * distFromCenter))) * 0.8;

      let zone: Vertex3D["zone"] = "skin";
      let isLandmark = false;

      // Nose bridge and tip (center column r=3..6, c=4)
      if (c === 4 && r >= 3 && r <= 6) {
        z += 0.35 - (r - 4) * 0.05;
        zone = "nose";
        isLandmark = true;
      }
      // Orbital eye sockets (r=3..4, c=2,6)
      if ((r === 3 || r === 4) && (c === 2 || c === 6)) {
        z -= 0.15;
        zone = "orbital";
        isLandmark = true;
      }
      // Zygomatic cheekbones (r=5..6, c=1,7)
      if ((r === 5 || r === 6) && (c === 1 || c === 7)) {
        z += 0.18;
        zone = "zygomatic";
        isLandmark = true;
      }
      // Jaw and chin (r=8..10)
      if (r >= 8) {
        zone = "jaw";
        if (c === 4 && r === 10) isLandmark = true;
      }
      // Forehead (r=0..2)
      if (r <= 2) {
        zone = "forehead";
      }

      vertices.push({ x, y, z, zone, isLandmark });
    }
  }

  // Create grid triangle edges
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const idx = r * cols + c;
      if (c < cols - 1) edges.push([idx, idx + 1]);
      if (r < rows - 1) edges.push([idx, idx + cols]);
      if (r < rows - 1 && c < cols - 1) edges.push([idx, idx + cols + 1]);
    }
  }

  return { vertices, edges };
}

const FACE_DATA = generateAnatomicalFaceMesh();

export const FaceMesh3D: React.FC<FaceMesh3DProps> = ({
  mode,
  showKeypoints = false,
  year = 2008,
  snrScore = 17.8,
  interactive = true,
  className = "",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [rotX, setRotX] = useState<number>(0.15); // Pitch
  const [rotY, setRotY] = useState<number>(-0.3); // Yaw
  const isDragging = useRef<boolean>(false);
  const lastMouse = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let autoSpin = !interactive; // subtle spin if not interactive

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      if (autoSpin) {
        setRotY((prev) => prev + 0.004);
      }

      const centerX = width / 2;
      const centerY = height / 2;
      const scale = Math.min(width, height) * 0.38;

      const cosX = Math.cos(rotX);
      const sinX = Math.sin(rotX);
      const cosY = Math.cos(rotY);
      const sinY = Math.sin(rotY);

      // Project vertices
      const projected = FACE_DATA.vertices.map((v) => {
        // Rotate Y (Yaw)
        const x1 = v.x * cosY - v.z * sinY;
        const z1 = v.x * sinY + v.z * cosY;

        // Rotate X (Pitch)
        const y2 = v.y * cosX - z1 * sinX;
        const z2 = v.y * sinX + z1 * cosX;

        // Perspective
        const persp = 3.5 / (3.5 - z2 * 0.5);
        const px = centerX + x1 * scale * persp;
        const py = centerY - y2 * scale * persp;

        return { px, py, pz: z2, orig: v };
      });

      // Draw mode-specific faces / edges
      ctx.lineWidth = 1;

      if (mode === "3d-solid" || mode === "uv-texture" || mode === "heatmap") {
        // Render shaded polygons
        const cols = 9;
        const rows = 11;
        for (let r = 0; r < rows - 1; r++) {
          for (let c = 0; c < cols - 1; c++) {
            const i1 = r * cols + c;
            const i2 = i1 + 1;
            const i3 = i1 + cols;
            const i4 = i3 + 1;

            const p1 = projected[i1];
            const p2 = projected[i2];
            const p3 = projected[i4];
            const p4 = projected[i3];

            // Painter's approx depth
            const avgZ = (p1.pz + p2.pz + p3.pz + p4.pz) / 4;
            const lighting = Math.min(1, Math.max(0.2, (avgZ + 1.2) / 2.2));

            ctx.beginPath();
            ctx.moveTo(p1.px, p1.py);
            ctx.lineTo(p2.px, p2.py);
            ctx.lineTo(p3.px, p3.py);
            ctx.lineTo(p4.px, p4.py);
            ctx.closePath();

            if (mode === "heatmap") {
              const zone = p1.orig.zone;
              if (zone === "nose" || zone === "zygomatic") {
                ctx.fillStyle = `rgba(244, 63, 94, ${lighting * 0.75})`; // Crimson red heatmap
              } else if (zone === "orbital") {
                ctx.fillStyle = `rgba(245, 158, 11, ${lighting * 0.65})`; // Amber warmth
              } else {
                ctx.fillStyle = `rgba(16, 24, 32, ${lighting * 0.9})`;
              }
              ctx.strokeStyle = "rgba(244, 63, 94, 0.35)";
            } else if (mode === "uv-texture") {
              // Textured skin tones
              const skinVal = Math.floor(lighting * 180);
              ctx.fillStyle = `rgb(${skinVal}, ${Math.floor(skinVal * 0.9)}, ${Math.floor(skinVal * 0.8)})`;
              ctx.strokeStyle = "rgba(30, 41, 59, 0.4)";
            } else {
              // 3d solid clay
              const grey = Math.floor(lighting * 190);
              ctx.fillStyle = `rgb(${grey}, ${grey + 10}, ${grey + 25})`;
              ctx.strokeStyle = "rgba(14, 116, 144, 0.25)";
            }

            ctx.fill();
            ctx.stroke();
          }
        }
      }

      if (mode === "3d-wireframe" || mode === "3d-solid") {
        // Draw wireframe edges
        FACE_DATA.edges.forEach(([idxA, idxB]) => {
          const a = projected[idxA];
          const b = projected[idxB];

          const avgZ = (a.pz + b.pz) / 2;
          const opacity = Math.min(0.9, Math.max(0.15, (avgZ + 1.2) / 2.2));

          ctx.beginPath();
          ctx.moveTo(a.px, a.py);
          ctx.lineTo(b.px, b.py);
          ctx.strokeStyle =
            mode === "3d-wireframe"
              ? `rgba(6, 182, 212, ${opacity})`
              : `rgba(56, 189, 248, ${opacity * 0.5})`;
          ctx.stroke();
        });
      }

      // Draw Keypoints Subset-91 overlay if requested
      if (showKeypoints) {
        projected.forEach((p) => {
          if (p.orig.isLandmark) {
            ctx.beginPath();
            ctx.arc(p.px, p.py, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = "#10b981"; // Emerald green sphere
            ctx.fill();
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [mode, showKeypoints, rotX, rotY, interactive]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!interactive) return;
    isDragging.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current || !interactive) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };

    setRotY((prev) => prev + dx * 0.01);
    setRotX((prev) => Math.max(-1.0, Math.min(1.0, prev + dy * 0.01)));
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  return (
    <div
      className={`relative rounded-lg overflow-hidden border border-[#1f2d3d] bg-[#080d12] select-none flex items-center justify-center ${className}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas
        ref={canvasRef}
        width={380}
        height={380}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      />

      {/* Overlay Badge inside canvas */}
      <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
        <span className="rounded bg-[#0b1117]/90 px-2 py-0.5 font-mono text-[10px] text-cyan-300 border border-[#1f2d3d]">
          BFM MESH 3DDFA_v3 ({year})
        </span>
        <span className="rounded bg-[#0b1117]/90 px-2 py-0.5 font-mono text-[10px] text-slate-300 border border-[#1f2d3d]">
          SNR: {snrScore}
        </span>
      </div>

      <div className="absolute bottom-3 right-3 font-mono text-[10px] text-slate-500 pointer-events-none">
        {interactive ? "Драг мышью: вращение 3D (Yaw/Pitch)" : "Авто-вращение"}
      </div>
    </div>
  );
};
