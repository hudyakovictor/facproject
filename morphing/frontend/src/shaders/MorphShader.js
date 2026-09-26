import * as THREE from 'three';

export const MorphShaderMaterialDefinition = {
  uniforms: {
    u_progress: { value: 0.0 },
    u_textureA: { value: null },
    u_textureB: { value: null },
    u_showHeatmap: { value: 0.0 },
    u_wireframeMode: { value: 0.0 },
    u_lightDirection: { value: new THREE.Vector3(0.5, 1.0, 1.5).normalize() },
  },

  vertexShader: `
    attribute vec3 positionB;
    attribute vec2 uvCoords;
    
    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vDiff;
    
    uniform float u_progress;

    void main() {
      vUv = uvCoords;
      
      // 1. Плавный GPU-морфинг вершин из Модели A в Модель B
      vec3 morphedPos = mix(position, positionB, u_progress);
      
      // 2. Локальная анатомическая разница формы черепа (для тепловой карты)
      vDiff = length(position - positionB);
      
      // Передача нормалей
      vNormalVec = normalize(normalMatrix * normal);
      
      gl_Position = projectionMatrix * modelViewMatrix * vec4(morphedPos, 1.0);
    }
  `,

  fragmentShader: `
    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vDiff;
    
    uniform sampler2D u_textureA;
    uniform sampler2D u_textureB;
    uniform float u_progress;
    uniform float u_showHeatmap;
    uniform float u_wireframeMode;
    uniform vec3 u_lightDirection;

    // Палитра тепловой карты: Синий (0mm) -> Зеленый (среднее) -> Красный (максимум)
    vec3 getHeatmapColor(float val) {
      float v = clamp(val * 18.0, 0.0, 1.0);
      vec3 col = vec3(0.0);
      col.r = clamp(2.0 * v - 0.5, 0.0, 1.0);
      col.g = clamp(1.0 - abs(2.0 * v - 1.0), 0.0, 1.0);
      col.b = clamp(1.0 - 2.0 * v, 0.0, 1.0);
      return col;
    }

    void main() {
      // 1. Блендинг улучшенных HD UV-текстур (uv_module)
      vec4 texA = texture2D(u_textureA, vUv);
      vec4 texB = texture2D(u_textureB, vUv);
      vec4 blendedTex = mix(texA, texB, u_progress);
      
      // 2. Мягкое затенение Ламберта
      float diffLight = max(dot(vNormalVec, u_lightDirection), 0.0);
      vec3 ambient = vec3(0.35);
      vec3 light = ambient + diffLight * vec3(0.65);
      
      vec3 finalColor = blendedTex.rgb * light;
      
      // 3. Режим тепловой карты различий черепа
      if (u_showHeatmap > 0.5) {
        vec3 heat = getHeatmapColor(vDiff);
        finalColor = mix(finalColor, heat, 0.75);
      }
      
      // 4. Режим сетки
      if (u_wireframeMode > 0.5) {
        finalColor = mix(finalColor, vec3(0.0, 1.0, 0.8), 0.4);
      }
      
      gl_FragColor = vec4(finalColor, 1.0);
    }
  `
};
