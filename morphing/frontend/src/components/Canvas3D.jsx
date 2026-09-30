import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { MorphShaderMaterialDefinition } from '../shaders/MorphShader';
import { catmullRomWeights, interpolateFlat } from '../utils/timeline';

function sequenceFrom(data, key, fallbackA, fallbackB) {
  if (Array.isArray(data?.[key]) && data[key].length >= 2) return data[key];
  return [fallbackA, fallbackB];
}

export default function Canvas3D({
  morphData,
  progress,
  blendMode = 'timeline',
  blendWeights = [1, 0, 0, 0],
  showLandmarks,
  showHeatmap,
  showUVDiff = false,
  wireframe,
  lighting,
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const materialRef = useRef(null);
  const landmarksPointsRef = useRef(null);
  const sequenceRef = useRef(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return undefined;
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e1017);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 50);
    camera.position.set(0, 0, 2.6);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.NoToneMapping;
    rendererRef.current = renderer;
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
      const w = Math.max(container.clientWidth, 1);
      const h = Math.max(container.clientHeight, 1);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      cancelAnimationFrame(reqId);
      window.removeEventListener('resize', handleResize);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement && container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
      sceneRef.current = null;
      rendererRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!morphData || !sceneRef.current) return undefined;
    const scene = sceneRef.current;
    const oldMesh = scene.getObjectByName('face_mesh');
    const oldPoints = scene.getObjectByName('landmarks_106');
    if (oldMesh) {
      oldMesh.geometry.dispose();
      oldMesh.material.dispose();
      scene.remove(oldMesh);
    }
    if (oldPoints) {
      oldPoints.geometry.dispose();
      oldPoints.material.dispose();
      scene.remove(oldPoints);
    }

    const vertices = sequenceFrom(morphData, 'sequence_vertices', morphData.vertices_a, morphData.vertices_b);
    const landmarks = sequenceFrom(morphData, 'sequence_landmarks', morphData.landmarks_106_a, morphData.landmarks_106_b);
    const textures = sequenceFrom(morphData, 'sequence_textures', morphData.texture_a_base64, morphData.texture_b_base64);
    const textureLoader = new THREE.TextureLoader();
    const loadedTextures = textures.slice(0, 4).map((source) => {
      const texture = textureLoader.load(source);
      texture.colorSpace = THREE.SRGBColorSpace;
      return texture;
    });
    while (loadedTextures.length < 4) loadedTextures.push(loadedTextures[loadedTextures.length - 1]);
    const diffTexture = morphData.texture_diff_base64
      ? textureLoader.load(morphData.texture_diff_base64)
      : loadedTextures[0];
    diffTexture.colorSpace = THREE.SRGBColorSpace;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices[0], 3));
    geometry.setAttribute('positionB', new THREE.Float32BufferAttribute(vertices[1] || vertices[0], 3));
    geometry.setAttribute('positionC', new THREE.Float32BufferAttribute(vertices[2] || vertices[0], 3));
    geometry.setAttribute('positionD', new THREE.Float32BufferAttribute(vertices[3] || vertices[vertices.length - 1], 3));
    geometry.setAttribute('uvCoords', new THREE.Float32BufferAttribute(morphData.uv_coords, 2));
    geometry.setIndex(morphData.triangles);
    geometry.computeVertexNormals();

    const material = new THREE.ShaderMaterial({
      ...MorphShaderMaterialDefinition,
      uniforms: {
        u_weights: { value: new THREE.Vector4(1, 0, 0, 0) },
        u_textureA: { value: loadedTextures[0] },
        u_textureB: { value: loadedTextures[1] },
        u_textureC: { value: loadedTextures[2] },
        u_textureD: { value: loadedTextures[3] },
        u_textureDiff: { value: diffTexture },
        u_showHeatmap: { value: showHeatmap ? 1 : 0 },
        u_showUVDiff: { value: showUVDiff ? 1 : 0 },
        u_wireframeMode: { value: wireframe ? 1 : 0 },
        u_lightDirection: { value: new THREE.Vector3(0.4, 0.8, 1.2).normalize() },
        u_useLighting: { value: lighting ? 1 : 0 },
      },
      side: THREE.DoubleSide,
      wireframe,
    });
    materialRef.current = material;
    sequenceRef.current = { vertices, landmarks, count: vertices.length, times: morphData.timeline?.keyframe_times || null };

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'face_mesh';
    scene.add(mesh);
    const landmarkGeometry = new THREE.BufferGeometry();
    landmarkGeometry.setAttribute('position', new THREE.Float32BufferAttribute(landmarks[0], 3));
    const landmarkMaterial = new THREE.PointsMaterial({ color: 0x00ffaa, size: 0.02, sizeAttenuation: true, transparent: true, opacity: 0.9 });
    const points = new THREE.Points(landmarkGeometry, landmarkMaterial);
    points.name = 'landmarks_106';
    points.visible = showLandmarks;
    landmarksPointsRef.current = points;
    scene.add(points);

    return () => {
      loadedTextures.forEach((texture, index) => { if (index > 0 || !morphData.texture_a_base64) texture.dispose(); });
      material.dispose();
      geometry.dispose();
      landmarkGeometry.dispose();
      landmarkMaterial.dispose();
    };
  }, [morphData]);

  useEffect(() => {
    const material = materialRef.current;
    if (material && sequenceRef.current) {
      const { count, landmarks, times } = sequenceRef.current;
      const weights = blendMode === 'blend'
        ? normalizeWeights(blendWeights, count)
        : catmullRomWeights(progress, count, times);
      material.uniforms.u_weights.value.set(...weights);
      material.uniforms.u_showHeatmap.value = showHeatmap ? 1 : 0;
      material.uniforms.u_showUVDiff.value = showUVDiff ? 1 : 0;
      material.uniforms.u_wireframeMode.value = wireframe ? 1 : 0;
      material.uniforms.u_useLighting.value = lighting ? 1 : 0;
      material.wireframe = wireframe;
      if (landmarksPointsRef.current) {
        const current = blendMode === 'blend'
          ? blendFlat(landmarks, weights)
          : interpolateFlat(landmarks, progress, count);
        landmarksPointsRef.current.geometry.setAttribute('position', new THREE.Float32BufferAttribute(current, 3));
        landmarksPointsRef.current.geometry.attributes.position.needsUpdate = true;
        landmarksPointsRef.current.visible = showLandmarks;
      }
    }
  }, [progress, blendMode, blendWeights, showHeatmap, showUVDiff, showLandmarks, wireframe, lighting]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
      <div style={{ position: 'absolute', bottom: '16px', left: '20px', background: 'rgba(15, 18, 26, 0.75)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', padding: '8px 16px', fontSize: '12px', color: '#9aa5b5', display: 'flex', gap: '14px', pointerEvents: 'none' }}>
        <span>🖱 <b>Вращение:</b> ЛКМ</span>
        <span>🔍 <b>Масштаб:</b> Колесо</span>
        <span>✋ <b>Панорама:</b> ПКМ</span>
      </div>
    </div>
  );
}

function blendFlat(values, weights) {
  const result = new Float32Array(values[0].length);
  values.forEach((value, index) => {
    if (!weights[index]) return;
    for (let position = 0; position < value.length; position += 1) result[position] += value[position] * weights[index];
  });
  return result;
}

function normalizeWeights(values, count) {
  const weights = Array.from({ length: 4 }, (_, index) => Math.max(0, Number(values[index] || 0)));
  const total = weights.slice(0, count).reduce((sum, value) => sum + value, 0) || 1;
  return weights.map((value, index) => index < count ? value / total : 0);
}
