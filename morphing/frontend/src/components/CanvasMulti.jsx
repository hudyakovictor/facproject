import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { MultiMorphShaderMaterialDefinition } from '../shaders/MultiMorphShader';

/**
 * Общий Three.js-канвас для Multi-Face Blend и Timeline-режимов (см.
 * MultiMorphShader.js). Геометрия строится один раз из общей топологии
 * (triangles/uv), а 4 позиционных/текстурных "слота" перепривязываются к
 * элементам ``data.vertices``/``data.textures`` по индексам ``slotIndices``
 * (обновление буферов только при смене индексов — не на каждый кадр).
 *
 * @param data           { triangles, uv_coords, vertices: string[][], textures: string[] }
 * @param slotIndices    [i0, i1, i2, i3] — какие элементы data.vertices/textures сейчас в слотах A/B/C/D
 * @param mode           'blend' (барицентрический) | 'timeline' (Catmull-Rom)
 * @param weights        [w0, w1, w2, w3] — веса для режима 'blend'
 * @param segT           локальный t сегмента для режима 'timeline'
 * @param activeMask     [1/0 x4] — сколько слотов реально активно (для heatmap 'blend')
 */
export default function CanvasMulti({
  data,
  slotIndices,
  mode = 'blend',
  weights = [1, 0, 0, 0],
  segT = 0,
  activeMask = [1, 1, 0, 0],
  showHeatmap = false,
  wireframe = false,
  lighting = false,
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const materialRef = useRef(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e1017);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 50);
    camera.position.set(0, 0, 2.6);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.NoToneMapping;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 1.0;
    controls.maxDistance = 6.0;

    const grid = new THREE.GridHelper(4, 20, 0x1f2430, 0x151922);
    grid.position.y = -0.8;
    scene.add(grid);

    let reqId;
    const animate = () => {
      reqId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      const w = container.clientWidth, h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(reqId);
      window.removeEventListener('resize', handleResize);
      if (renderer.domElement && container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  // Геометрия + текстуры: пересобираются при смене данных или слотов (не каждый кадр)
  useEffect(() => {
    if (!data || !sceneRef.current) return;
    const scene = sceneRef.current;
    const prevMesh = scene.getObjectByName('multi_face_mesh');
    if (prevMesh) {
      prevMesh.geometry.dispose();
      if (prevMesh.material.uniforms) {
        ['u_tex0', 'u_tex1', 'u_tex2', 'u_tex3'].forEach((k) => {
          const t = prevMesh.material.uniforms[k]?.value;
          if (t) t.dispose();
        });
      }
      scene.remove(prevMesh);
    }

    const loader = new THREE.TextureLoader();
    const slots = slotIndices.map((idx) => (idx !== null && idx !== undefined ? idx : 0));
    const texSlots = slots.map((idx) => {
      const tex = loader.load(data.textures[idx] || data.textures[0]);
      tex.colorSpace = THREE.SRGBColorSpace;
      return tex;
    });
    const posSlots = slots.map((idx) => data.vertices[idx] || data.vertices[0]);

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(posSlots[0], 3));
    geometry.setAttribute('positionB', new THREE.Float32BufferAttribute(posSlots[1], 3));
    geometry.setAttribute('positionC', new THREE.Float32BufferAttribute(posSlots[2], 3));
    geometry.setAttribute('positionD', new THREE.Float32BufferAttribute(posSlots[3], 3));
    geometry.setAttribute('uvCoords', new THREE.Float32BufferAttribute(data.uv_coords, 2));
    geometry.setIndex(data.triangles);
    geometry.computeVertexNormals();

    const material = new THREE.ShaderMaterial({
      ...MultiMorphShaderMaterialDefinition,
      uniforms: {
        u_mode: { value: mode === 'timeline' ? 1.0 : 0.0 },
        u_weights: { value: new THREE.Vector4(...weights) },
        u_segT: { value: segT },
        u_tex0: { value: texSlots[0] },
        u_tex1: { value: texSlots[1] },
        u_tex2: { value: texSlots[2] },
        u_tex3: { value: texSlots[3] },
        u_showHeatmap: { value: showHeatmap ? 1.0 : 0.0 },
        u_activeMask: { value: new THREE.Vector4(...activeMask) },
        u_wireframeMode: { value: wireframe ? 1.0 : 0.0 },
        u_lightDirection: { value: new THREE.Vector3(0.4, 0.8, 1.2).normalize() },
        u_useLighting: { value: lighting ? 1.0 : 0.0 },
      },
      side: THREE.DoubleSide,
      wireframe,
    });
    materialRef.current = material;

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'multi_face_mesh';
    scene.add(mesh);
  }, [data, JSON.stringify(slotIndices)]);

  // Обновление uniforms в реальном времени (веса, segT, режимы отображения)
  useEffect(() => {
    if (!materialRef.current) return;
    const u = materialRef.current.uniforms;
    u.u_mode.value = mode === 'timeline' ? 1.0 : 0.0;
    u.u_weights.value.set(...weights);
    u.u_segT.value = segT;
    u.u_showHeatmap.value = showHeatmap ? 1.0 : 0.0;
    u.u_activeMask.value.set(...activeMask);
    u.u_wireframeMode.value = wireframe ? 1.0 : 0.0;
    u.u_useLighting.value = lighting ? 1.0 : 0.0;
    materialRef.current.wireframe = wireframe;
  }, [mode, weights, segT, showHeatmap, activeMask, wireframe, lighting]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      <div style={{
        position: 'absolute', bottom: '16px', left: '20px',
        background: 'rgba(15, 18, 26, 0.75)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px',
        padding: '8px 16px', fontSize: '12px', color: '#9aa5b5',
        display: 'flex', gap: '14px', pointerEvents: 'none'
      }}>
        <span>🖱 <b>Вращение:</b> ЛКМ</span>
        <span>🔍 <b>Масштаб:</b> Колесо</span>
        <span>✋ <b>Панорама:</b> ПКМ</span>
      </div>
    </div>
  );
}
