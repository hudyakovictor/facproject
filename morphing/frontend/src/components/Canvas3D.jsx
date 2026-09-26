import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { MorphShaderMaterialDefinition } from '../shaders/MorphShader';

export default function Canvas3D({
  morphData,
  progress,
  showLandmarks,
  showHeatmap,
  wireframe,
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const materialRef = useRef(null);
  const landmarksPointsRef = useRef(null);

  // Инициализация Three.js сцены
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
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    rendererRef.current = renderer;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 1.0;
    controls.maxDistance = 6.0;

    // Сетка пола
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
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(reqId);
      window.removeEventListener('resize', handleResize);
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Загрузка и привязка данных морфинга
  useEffect(() => {
    if (!morphData || !sceneRef.current) return;
    const scene = sceneRef.current;

    // Удаляем старые объекты
    const prevMesh = scene.getObjectByName('face_mesh');
    if (prevMesh) scene.remove(prevMesh);
    const prevPoints = scene.getObjectByName('landmarks_106');
    if (prevPoints) scene.remove(prevPoints);

    // Загрузка HD UV текстур (uv_module)
    const loader = new THREE.TextureLoader();
    const texA = loader.load(morphData.texture_a_base64);
    const texB = loader.load(morphData.texture_b_base64);
    texA.colorSpace = THREE.SRGBColorSpace;
    texB.colorSpace = THREE.SRGBColorSpace;

    // Создание морфинг-геометрии (35 709 вершин)
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(morphData.vertices_a, 3));
    geometry.setAttribute('positionB', new THREE.Float32BufferAttribute(morphData.vertices_b, 3));
    geometry.setAttribute('uvCoords', new THREE.Float32BufferAttribute(morphData.uv_coords, 2));
    geometry.setIndex(morphData.triangles);
    geometry.computeVertexNormals();

    // Шейдерный материал
    const material = new THREE.ShaderMaterial({
      ...MorphShaderMaterialDefinition,
      uniforms: {
        u_progress: { value: progress },
        u_textureA: { value: texA },
        u_textureB: { value: texB },
        u_showHeatmap: { value: showHeatmap ? 1.0 : 0.0 },
        u_wireframeMode: { value: wireframe ? 1.0 : 0.0 },
        u_lightDirection: { value: new THREE.Vector3(0.4, 0.8, 1.2).normalize() },
      },
      side: THREE.DoubleSide,
      wireframe: wireframe,
    });
    materialRef.current = material;

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'face_mesh';
    scene.add(mesh);

    // Создание 106 3D ориентиров лица
    const ldmGeo = new THREE.BufferGeometry();
    ldmGeo.setAttribute('position', new THREE.Float32BufferAttribute(morphData.landmarks_106_a, 3));
    const ldmMat = new THREE.PointsMaterial({
      color: 0x00ffaa,
      size: 0.02,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.9,
    });
    const ldmPoints = new THREE.Points(ldmGeo, ldmMat);
    ldmPoints.name = 'landmarks_106';
    ldmPoints.visible = showLandmarks;
    landmarksPointsRef.current = ldmPoints;
    scene.add(ldmPoints);

  }, [morphData]);

  // Обновление состояния морфинга в реальном времени
  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.u_progress.value = progress;
      materialRef.current.uniforms.u_showHeatmap.value = showHeatmap ? 1.0 : 0.0;
      materialRef.current.uniforms.u_wireframeMode.value = wireframe ? 1.0 : 0.0;
      materialRef.current.wireframe = wireframe;
    }

    // Морфинг 106 ориентиров
    if (morphData && landmarksPointsRef.current) {
      const a = morphData.landmarks_106_a;
      const b = morphData.landmarks_106_b;
      const interp = new Float32Array(a.length);
      for (let i = 0; i < a.length; i++) {
        interp[i] = a[i] * (1 - progress) + b[i] * progress;
      }
      landmarksPointsRef.current.geometry.setAttribute('position', new THREE.Float32BufferAttribute(interp, 3));
      landmarksPointsRef.current.geometry.attributes.position.needsUpdate = true;
      landmarksPointsRef.current.visible = showLandmarks;
    }
  }, [progress, showHeatmap, showLandmarks, wireframe]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      
      {/* Подсказка управления */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '20px',
        background: 'rgba(15, 18, 26, 0.75)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '8px',
        padding: '8px 16px',
        fontSize: '12px',
        color: '#9aa5b5',
        display: 'flex',
        gap: '14px',
        pointerEvents: 'none'
      }}>
        <span>🖱 <b>Вращение:</b> ЛКМ</span>
        <span>🔍 <b>Масштаб:</b> Колесо</span>
        <span>✋ <b>Панорама:</b> ПКМ</span>
      </div>
    </div>
  );
}
