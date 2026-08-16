import { useEffect, useRef, useState } from 'react';
import type { TimelinePhoto } from '../../types/timeline';

/**
 * 3D Face Model Viewer Component.
 * Displays a simplified 3D representation of face landmarks.
 * Uses Canvas 2D for projection (WebGL/Three.js can be added later).
 */

interface ModelViewer3DProps {
  photo: TimelinePhoto | null;
  width: number;
  height: number;
}

// Simplified face landmark positions (normalized 0-1)
// Based on LDM106 landmark topology
const FACE_LANDMARKS = {
  // Jaw line (0-16)
  jaw: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
  // Right eyebrow (17-21)
  rightEyebrow: [17, 18, 19, 20, 21],
  // Left eyebrow (22-26)
  leftEyebrow: [22, 23, 24, 25, 26],
  // Nose bridge (27-30)
  noseBridge: [27, 28, 29, 30],
  // Nose tip (31-35)
  noseTip: [31, 32, 33, 34, 35],
  // Right eye (36-41)
  rightEye: [36, 37, 38, 39, 40, 41],
  // Left eye (42-47)
  leftEye: [42, 43, 44, 45, 46, 47],
  // Outer lip (48-59)
  outerLip: [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59],
  // Inner lip (60-67)
  innerLip: [60, 61, 62, 63, 64, 65, 66, 67],
};

// Generate pseudo-3D coordinates based on photo metrics
function generateLandmarkPositions(photo: TimelinePhoto): Array<{ x: number; y: number; z: number }> {
  const positions: Array<{ x: number; y: number; z: number }> = [];
  
  // Base face shape influenced by bone score and symmetry
  const boneFactor = photo.boneScore ?? 0.5;
  const symmetryFactor = photo.symmetry ?? 0.5;
  const yaw = (photo.yaw ?? 0) * Math.PI / 180;
  const pitch = (photo.pitch ?? 0) * Math.PI / 180;
  
  // Generate 68 landmark positions (simplified model)
  for (let i = 0; i < 68; i++) {
    let x = 0.5, y = 0.5, z = 0;
    
    // Jaw line
    if (i <= 16) {
      const t = i / 16;
      x = 0.2 + t * 0.6;
      y = 0.7 + Math.sin(t * Math.PI) * 0.15 * boneFactor;
      z = Math.sin(t * Math.PI) * 0.1;
    }
    // Eyebrows
    else if (i <= 26) {
      const isRight = i <= 21;
      const t = isRight ? (i - 17) / 4 : (i - 22) / 4;
      x = isRight ? 0.25 + t * 0.15 : 0.6 + t * 0.15;
      y = 0.3 + Math.sin(t * Math.PI) * 0.03;
      z = 0.05;
    }
    // Nose
    else if (i <= 35) {
      const t = i <= 30 ? (i - 27) / 3 : (i - 31) / 4;
      x = 0.45 + t * 0.1;
      y = i <= 30 ? 0.35 + t * 0.15 : 0.5 + t * 0.08;
      z = i <= 30 ? 0.1 + t * 0.1 : 0.15;
    }
    // Eyes
    else if (i <= 47) {
      const isRight = i <= 41;
      const t = (i - (isRight ? 36 : 42)) / 5;
      const centerX = isRight ? 0.32 : 0.68;
      x = centerX + Math.cos(t * Math.PI * 2) * 0.05;
      y = 0.38 + Math.sin(t * Math.PI * 2) * 0.02;
      z = 0.08;
    }
    // Lips
    else if (i <= 67) {
      const isOuter = i <= 59;
      const t = (i - (isOuter ? 48 : 60)) / (isOuter ? 11 : 7);
      const radius = isOuter ? 0.08 : 0.05;
      x = 0.5 + Math.cos(t * Math.PI * 2) * radius;
      y = 0.62 + Math.sin(t * Math.PI * 2) * radius * 0.5;
      z = 0.05;
    }
    
    // Apply rotation based on pose
    const rotatedX = (x - 0.5) * Math.cos(yaw) + (z) * Math.sin(yaw) + 0.5;
    const rotatedY = (y - 0.5) * Math.cos(pitch) + (z) * Math.sin(pitch) + 0.5;
    
    // Apply symmetry factor
    const finalX = 0.5 + (rotatedX - 0.5) * (0.8 + symmetryFactor * 0.2);
    const finalY = rotatedY;
    const finalZ = z * boneFactor;
    
    positions.push({ x: finalX, y: finalY, z: finalZ });
  }
  
  return positions;
}

export function ModelViewer3D({ photo, width, height }: ModelViewer3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [rotation, setRotation] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const lastMouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !photo) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Clear
    ctx.fillStyle = 'var(--bg-canvas)';
    ctx.fillRect(0, 0, width, height);

    const positions = generateLandmarkPositions(photo);
    const centerX = width / 2;
    const centerY = height / 2;
    const scale = Math.min(width, height) * 0.8;

    // Apply rotation
    const rotX = rotation.x * Math.PI / 180;
    const rotY = rotation.y * Math.PI / 180;

    // Transform 3D to 2D
    const projected = positions.map(p => {
      // Rotate around Y axis
      let x = (p.x - 0.5) * Math.cos(rotY) + p.z * Math.sin(rotY);
      let z = -(p.x - 0.5) * Math.sin(rotY) + p.z * Math.cos(rotY);
      
      // Rotate around X axis
      let y = (p.y - 0.5) * Math.cos(rotX) - z * Math.sin(rotX);
      z = (p.y - 0.5) * Math.sin(rotX) + z * Math.cos(rotX);
      
      // Project to 2D
      const perspective = 1 / (1 + z * 0.5);
      return {
        x: centerX + x * scale * perspective,
        y: centerY + y * scale * perspective,
        z: z,
      };
    });

    // Sort by z for proper rendering
    const sortedIndices = projected.map((_, i) => i).sort((a, b) => projected[a]!.z - projected[b]!.z);

    // Draw connections
    const drawConnection = (indices: number[], color: string) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      for (let i = 0; i < indices.length; i++) {
        const idx = indices[i]!;
        const p = projected[idx];
        if (!p) continue;
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    };

    // Draw face mesh
    ctx.globalAlpha = 0.6;
    drawConnection(FACE_LANDMARKS.jaw, 'var(--metric-geometry)');
    drawConnection(FACE_LANDMARKS.rightEyebrow, 'var(--metric-geometry)');
    drawConnection(FACE_LANDMARKS.leftEyebrow, 'var(--metric-geometry)');
    drawConnection(FACE_LANDMARKS.noseBridge, 'var(--metric-geometry)');
    drawConnection(FACE_LANDMARKS.noseTip, 'var(--metric-geometry)');
    drawConnection(FACE_LANDMARKS.rightEye, 'var(--color-info)');
    drawConnection(FACE_LANDMARKS.leftEye, 'var(--color-info)');
    drawConnection(FACE_LANDMARKS.outerLip, 'var(--color-warning)');
    drawConnection(FACE_LANDMARKS.innerLip, 'var(--color-warning)');

    // Draw points
    ctx.globalAlpha = 1;
    for (const i of sortedIndices) {
      const p = projected[i]!;
      const depth = (p.z + 0.5) / 1; // Normalize depth
      const size = 2 + depth * 2;
      
      ctx.beginPath();
      ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(96, 165, 250, ${0.4 + depth * 0.6})`;
      ctx.fill();
    }

    // Draw axes indicator
    ctx.fillStyle = 'var(--text-muted)';
    ctx.font = '10px var(--font-mono)';
    ctx.fillText('3D Model (LDM68)', 8, 16);
    ctx.fillText(`Yaw: ${(photo.yaw ?? 0).toFixed(1)}°`, 8, height - 24);
    ctx.fillText(`Pitch: ${(photo.pitch ?? 0).toFixed(1)}°`, 8, height - 12);

  }, [photo, width, height, rotation]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - lastMouseRef.current.x;
    const dy = e.clientY - lastMouseRef.current.y;
    setRotation(r => ({
      x: Math.max(-90, Math.min(90, r.x + dy * 0.5)),
      y: r.y + dx * 0.5,
    }));
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  if (!photo) {
    return (
      <div className="model-viewer-empty" style={{ width, height }}>
        <span>Выберите кадр для 3D просмотра</span>
      </div>
    );
  }

  return (
    <div className="model-viewer" style={{ width, height }}>
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      />
      <div className="model-viewer-hint">
        Перетаскивание — вращение модели
      </div>
    </div>
  );
}
