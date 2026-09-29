import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { pcaProject } from '../lib/pca';

/**
 * 🌌 Face Space Scatter — 3D PCA-скаттер пространства форм лиц (M12/M29).
 *
 * Урезанная (session-only) версия исходной идеи "3D Scatter Plot всего
 * датасета лиц с кликом для морфинга": здесь нет доступа к Stage 1
 * датасету, поэтому точки — только лица, загруженные в текущей сессии
 * (2-6 alpha_id векторов из /api/morph-multi). PCA считается ТОЧНО через
 * Gram-матрицу (lib/pca.js, JacobiEigen) — не приближение.
 *
 * @param alphaVectors  N x 80 массив (alpha_id каждого лица)
 * @param labels        N строк (напр. ['A','B','C'])
 * @param colors        N HEX-цветов
 * @param selectedIndex текущий "доминирующий" индекс (для подсветки)
 * @param onSelect      (index) => void — клик по точке
 */
export default function FaceSpaceScatter({ alphaVectors, labels, colors, selectedIndex, onSelect }) {
  const mountRef = useRef(null);
  const stateRef = useRef({});

  useEffect(() => {
    const container = mountRef.current;
    if (!container || !alphaVectors || alphaVectors.length < 2) return;

    const { coords, explainedVariance } = pcaProject(alphaVectors, 3);
    // нормируем на некий разумный радиус сцены
    let maxAbs = 1e-6;
    for (const c of coords) for (const v of c) maxAbs = Math.max(maxAbs, Math.abs(v));
    const scale = 0.8 / maxAbs;

    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 50);
    camera.position.set(1.6, 1.2, 1.6);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    scene.add(new THREE.AxesHelper(1.0));
    scene.add(new THREE.GridHelper(2, 10, 0x30363d, 0x1f2430));

    const spheres = coords.map((c, i) => {
      const geo = new THREE.SphereGeometry(0.06, 20, 20);
      const mat = new THREE.MeshBasicMaterial({ color: colors?.[i] || '#58a6ff' });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(c[0] * scale, c[1] * scale, c[2] * scale);
      mesh.userData.index = i;
      scene.add(mesh);
      return mesh;
    });

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const onClick = (ev) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(spheres);
      if (hits.length > 0 && onSelect) onSelect(hits[0].object.userData.index);
    };
    renderer.domElement.addEventListener('click', onClick);

    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      spheres.forEach((s, i) => {
        const sel = i === selectedIndexRef.current;
        s.scale.setScalar(sel ? 1.6 : 1.0);
      });
      controls.update();
      renderer.render(scene, camera);
    };
    const selectedIndexRef = { current: selectedIndex };
    stateRef.current.selectedIndexRef = selectedIndexRef;
    animate();

    const onResize = () => {
      const w = container.clientWidth, h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    stateRef.current.explainedVariance = explainedVariance;
    stateRef.current.cleanup = () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      renderer.domElement.removeEventListener('click', onClick);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };

    return () => stateRef.current.cleanup?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alphaVectors, colors]);

  useEffect(() => {
    if (stateRef.current.selectedIndexRef) stateRef.current.selectedIndexRef.current = selectedIndex;
  }, [selectedIndex]);

  return (
    <div>
      <div ref={mountRef} style={{ width: '100%', height: '220px', borderRadius: '8px', overflow: 'hidden', cursor: 'pointer' }} />
      <div style={{ fontSize: '10px', color: '#6e7681', marginTop: '6px', lineHeight: 1.4 }}>
        Точки — только {alphaVectors?.length || 0} лиц(о) этой сессии, спроецированные PCA из
        80-мерного пространства формы (α_id) в 3D. Клик по точке → 100% вес этому лицу.
        {labels?.map((l, i) => ` ${l}=${colors?.[i]}`).join('') ? '' : ''}
      </div>
    </div>
  );
}
