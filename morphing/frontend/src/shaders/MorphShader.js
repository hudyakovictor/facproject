import * as THREE from 'three';

export const MorphShaderMaterialDefinition = {
  uniforms: {
    u_progress: { value: 0.0 },
    u_textureA: { value: null },
    u_textureB: { value: null },
    u_showHeatmap: { value: 0.0 },
    u_heatmapSource: { value: 0.0 }, // 0 = |A-B| diff, 1 = |deltaA| (уникальность A), 2 = |deltaB| (уникальность B)
    u_wireframeMode: { value: 0.0 },
    u_lightDirection: { value: new THREE.Vector3(0.5, 1.0, 1.5).normalize() },
    u_useLighting: { value: 0.0 },
    u_showUVDiff: { value: 0.0 },
    // Identity Decomposition: V(t) = V_mean + tA*deltaA + tB*deltaB
    u_decompMode: { value: 0.0 }, // 0 = обычный линейный морф A<->B, 1 = decomposition
    u_tA: { value: 1.0 },
    u_tB: { value: 0.0 },
  },

  vertexShader: `
    attribute vec3 positionB;
    attribute vec2 uvCoords;
    // Identity Decomposition attributes (см. App.jsx/Canvas3D.jsx):
    // positionMean = среднее лицо модели BFM (identity=0, exp=0);
    // deltaA = V_a - V_mean, deltaB = V_b - V_mean.
    attribute vec3 positionMean;
    attribute vec3 deltaA;
    attribute vec3 deltaB;
    
    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vDiff;
    varying float vDeltaAMag;
    varying float vDeltaBMag;
    
    uniform float u_progress;
    uniform float u_decompMode;
    uniform float u_tA;
    uniform float u_tB;

    void main() {
      vUv = uvCoords;
      
      // 1. Плавный GPU-морфинг вершин из Модели A в Модель B
      vec3 pairPos = mix(position, positionB, u_progress);

      // 1b. Identity Decomposition: V = V_mean + tA*deltaA + tB*deltaB
      vec3 decompPos = positionMean + u_tA * deltaA + u_tB * deltaB;

      vec3 morphedPos = mix(pairPos, decompPos, u_decompMode);
      
      // 2. Локальная анатомическая разница формы черепа (для тепловой карты)
      vDiff = length(position - positionB);
      vDeltaAMag = length(deltaA);
      vDeltaBMag = length(deltaB);
      
      // Передача нормалей
      vNormalVec = normalize(normalMatrix * normal);
      
      gl_Position = projectionMatrix * modelViewMatrix * vec4(morphedPos, 1.0);
    }
  `,

  fragmentShader: `
    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vDiff;
    varying float vDeltaAMag;
    varying float vDeltaBMag;
    
    uniform sampler2D u_textureA;
    uniform sampler2D u_textureB;
    uniform float u_progress;
    uniform float u_showHeatmap;
    uniform float u_heatmapSource;
    uniform float u_wireframeMode;
    uniform float u_useLighting;
    uniform vec3 u_lightDirection;
    uniform float u_showUVDiff;
    uniform float u_decompMode;
    uniform float u_tA;
    uniform float u_tB;

    // Палитра тепловой карты: Синий (0mm) -> Зеленый (среднее) -> Красный (максимум)
    vec3 getHeatmapColor(float val) {
      float v = clamp(val * 18.0, 0.0, 1.0);
      vec3 col = vec3(0.0);
      col.r = clamp(2.0 * v - 0.5, 0.0, 1.0);
      col.g = clamp(1.0 - abs(2.0 * v - 1.0), 0.0, 1.0);
      col.b = clamp(1.0 - 2.0 * v, 0.0, 1.0);
      return col;
    }

    // Константы палитр заданы в sRGB, а three.js работает в линейном пространстве.
    vec3 srgbToLinear(vec3 c) {
      return pow(c, vec3(2.2));
    }

    void main() {
      // 1. Блендинг улучшенных HD UV-текстур (uv_module).
      // В обычном режиме — по u_progress; в Identity Decomposition — по
      // относительному вкладу tB/(tA+tB), чтобы текстура следовала за
      // теми же слайдерами, что и форма.
      vec4 texA = texture2D(u_textureA, vUv);
      vec4 texB = texture2D(u_textureB, vUv);
      float decompTexT = clamp(u_tB / (u_tA + u_tB + 1e-5), 0.0, 1.0);
      float texT = mix(u_progress, decompTexT, u_decompMode);
      vec4 blendedTex = mix(texA, texB, texT);
      
      // 2. Мягкое затенение Ламберта (свет закреплён на камере).
      //    u_useLighting = 0 -> цвет берётся прямо из UV-текстуры, как на фото.
      float diffLight = max(dot(normalize(vNormalVec), u_lightDirection), 0.0);
      vec3 lit = vec3(0.45) + diffLight * vec3(0.55);
      
      vec3 finalColor = blendedTex.rgb * mix(vec3(1.0), lit, u_useLighting);
      
      // 3. Режим тепловой карты различий черепа (3 источника, см. u_heatmapSource)
      if (u_showHeatmap > 0.5) {
        float heatVal = vDiff;
        if (u_heatmapSource > 1.5) {
          heatVal = vDeltaBMag;
        } else if (u_heatmapSource > 0.5) {
          heatVal = vDeltaAMag;
        }
        vec3 heat = srgbToLinear(getHeatmapColor(heatVal));
        finalColor = mix(finalColor, heat, 0.75);
      }

      // 3b. UV Diff: |texA - texB| по пикселям — разница текстуры кожи (пигментация,
      // морщины, структура), НЕ зависит от прогресса морфа формы. Общая UV-развёртка
      // (M18) делает пиксель-пиксельное сравнение корректным по построению.
      if (u_showUVDiff > 0.5) {
        vec3 diffTex = abs(texA.rgb - texB.rgb);
        float m = max(max(diffTex.r, diffTex.g), diffTex.b);
        finalColor = srgbToLinear(getHeatmapColor(m * 4.0));
      }
      
      // 4. Режим сетки
      if (u_wireframeMode > 0.5) {
        finalColor = mix(finalColor, srgbToLinear(vec3(0.0, 1.0, 0.8)), 0.4);
      }
      
      gl_FragColor = vec4(finalColor, 1.0);
      // Обязательные чанки three.js: тонмаппинг и перевод из линейного пространства
      // в пространство вывода. Без них в пиксель уходит T^2.4 вместо T — лицо
      // тёмное, перенасыщенное («кислотное») и не совпадает с фото.
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }
  `
};
