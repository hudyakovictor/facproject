import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export default function FaceSpacePlot({ faceSpace }) {
  const mountRef = useRef(null);
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !faceSpace?.points?.length) return undefined;
    const width = Math.max(mount.clientWidth, 240);
    const height = 190;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 100);
    camera.position.set(0, 0, 2.8);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    const coords = faceSpace.points.map((point) => new THREE.Vector3(point.x, point.y, point.z));
    const extent = Math.max(...coords.map((point) => point.length()), 1e-6);
    const scale = 0.85 / extent;
    coords.forEach((point) => point.multiplyScalar(scale));
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(coords), new THREE.LineBasicMaterial({ color: 0x58a6ff, transparent: true, opacity: 0.55 }));
    scene.add(line);
    coords.forEach((point, index) => {
      const geometry = new THREE.SphereGeometry(index < 2 ? 0.065 : 0.04, 12, 8);
      const material = new THREE.MeshBasicMaterial({ color: index === 0 ? 0x00ffaa : index === 1 ? 0xff7b72 : 0xd2a8ff });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(point);
      scene.add(mesh);
    });
    let animation;
    const render = () => { animation = requestAnimationFrame(render); controls.update(); renderer.render(scene, camera); };
    render();
    return () => { cancelAnimationFrame(animation); controls.dispose(); scene.traverse((item) => { item.geometry?.dispose(); item.material?.dispose(); }); renderer.dispose(); if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement); };
  }, [faceSpace]);

  return (
    <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8b949e', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase' }}>
        <span>📊 3D Face Space · PCA</span><span>{(faceSpace.explained_variance?.[0] * 100 || 0).toFixed(1)}% PC1</span>
      </div>
      <div ref={mountRef} style={{ height: '190px', width: '100%', marginTop: '6px', borderRadius: '6px', overflow: 'hidden' }} />
      <div style={{ color: '#8b949e', fontSize: '10px', marginTop: '5px' }}>● A&nbsp;&nbsp; ● B&nbsp;&nbsp; линия — порядок timeline. Вращайте сцену мышью.</div>
    </div>
  );
}
