import * as THREE from 'three';

/**
 * Единый шейдер для двух N-лицевых режимов подпроекта morphing:
 *
 *  - u_mode = 0 → **Multi-Face Blend** (до 4 лиц): барицентрический блендинг
 *    V = w0*P0 + w1*P1 + w2*P2 + w3*P3, где w0..w3 — веса (Σw = 1),
 *    заданные UI (треугольный барицентрический пикер для 3 лиц, линейные
 *    нормированные слайдеры для 4).
 *
 *  - u_mode = 1 → **Timeline A→B→C→D** (Catmull-Rom по вершинам): атрибуты
 *    переинтерпретируются как 4 СОСЕДНИЕ контрольные точки текущего
 *    сегмента (P0=предыдущая, P1=начало сегмента, P2=конец сегмента,
 *    P3=следующая), u_segT — локальный параметр [0,1] внутри сегмента.
 *    Текстура в этом режиме — линейный кроссфейд между текстурами P1/P2
 *    (форма гладкая по сплайну, текстура — по ближайшим двум фото).
 *
 * Общая топология (triangles/uv) для всех N лиц — один draw call.
 */
export const MultiMorphShaderMaterialDefinition = {
  uniforms: {
    u_mode: { value: 0.0 },
    u_weights: { value: new THREE.Vector4(1, 0, 0, 0) },
    u_segT: { value: 0.0 },
    u_tex0: { value: null },
    u_tex1: { value: null },
    u_tex2: { value: null },
    u_tex3: { value: null },
    u_showHeatmap: { value: 0.0 },
    u_activeMask: { value: new THREE.Vector4(1, 1, 0, 0) },
    u_wireframeMode: { value: 0.0 },
    u_lightDirection: { value: new THREE.Vector3(0.4, 0.8, 1.2).normalize() },
    u_useLighting: { value: 0.0 },
  },

  vertexShader: `
    attribute vec3 positionB;
    attribute vec3 positionC;
    attribute vec3 positionD;
    attribute vec2 uvCoords;

    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vSpreadMag;

    uniform float u_mode;
    uniform vec4 u_weights;
    uniform float u_segT;
    uniform vec4 u_activeMask;

    // Catmull-Rom (uniform, tension 0.5) через 4 контрольные точки.
    vec3 catmullRom(vec3 p0, vec3 p1, vec3 p2, vec3 p3, float t) {
      float t2 = t * t;
      float t3 = t2 * t;
      return 0.5 * (
        (2.0 * p1) +
        (-p0 + p2) * t +
        (2.0*p0 - 5.0*p1 + 4.0*p2 - p3) * t2 +
        (-p0 + 3.0*p1 - 3.0*p2 + p3) * t3
      );
    }

    void main() {
      vUv = uvCoords;

      vec3 barycentricPos = position * u_weights.x + positionB * u_weights.y
                           + positionC * u_weights.z + positionD * u_weights.w;
      vec3 catmullPos = catmullRom(position, positionB, positionC, positionD, u_segT);
      vec3 morphedPos = mix(barycentricPos, catmullPos, u_mode);

      // "Разброс" вершины между активными лицами — для heatmap N-лицевого режима:
      // среднеквадратичное отклонение от среднего по активным позициям.
      float nActive = max(u_activeMask.x + u_activeMask.y + u_activeMask.z + u_activeMask.w, 1.0);
      vec3 meanPos = (position * u_activeMask.x + positionB * u_activeMask.y
                    + positionC * u_activeMask.z + positionD * u_activeMask.w) / nActive;
      float sq = u_activeMask.x * dot(position - meanPos, position - meanPos)
               + u_activeMask.y * dot(positionB - meanPos, positionB - meanPos)
               + u_activeMask.z * dot(positionC - meanPos, positionC - meanPos)
               + u_activeMask.w * dot(positionD - meanPos, positionD - meanPos);
      vSpreadMag = sqrt(sq / nActive);

      vNormalVec = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(morphedPos, 1.0);
    }
  `,

  fragmentShader: `
    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vSpreadMag;

    uniform sampler2D u_tex0;
    uniform sampler2D u_tex1;
    uniform sampler2D u_tex2;
    uniform sampler2D u_tex3;
    uniform float u_mode;
    uniform vec4 u_weights;
    uniform float u_segT;
    uniform float u_showHeatmap;
    uniform float u_wireframeMode;
    uniform float u_useLighting;
    uniform vec3 u_lightDirection;

    vec3 getHeatmapColor(float val) {
      float v = clamp(val * 18.0, 0.0, 1.0);
      vec3 col = vec3(0.0);
      col.r = clamp(2.0 * v - 0.5, 0.0, 1.0);
      col.g = clamp(1.0 - abs(2.0 * v - 1.0), 0.0, 1.0);
      col.b = clamp(1.0 - 2.0 * v, 0.0, 1.0);
      return col;
    }

    vec3 srgbToLinear(vec3 c) {
      return pow(c, vec3(2.2));
    }

    void main() {
      vec4 t0 = texture2D(u_tex0, vUv);
      vec4 t1 = texture2D(u_tex1, vUv);
      vec4 t2 = texture2D(u_tex2, vUv);
      vec4 t3 = texture2D(u_tex3, vUv);

      vec4 barycentricTex = t0 * u_weights.x + t1 * u_weights.y + t2 * u_weights.z + t3 * u_weights.w;
      vec4 catmullTex = mix(t1, t2, u_segT);
      vec4 blendedTex = mix(barycentricTex, catmullTex, u_mode);

      float diffLight = max(dot(normalize(vNormalVec), u_lightDirection), 0.0);
      vec3 lit = vec3(0.45) + diffLight * vec3(0.55);
      vec3 finalColor = blendedTex.rgb * mix(vec3(1.0), lit, u_useLighting);

      if (u_showHeatmap > 0.5) {
        vec3 heat = srgbToLinear(getHeatmapColor(vSpreadMag));
        finalColor = mix(finalColor, heat, 0.75);
      }

      if (u_wireframeMode > 0.5) {
        finalColor = mix(finalColor, srgbToLinear(vec3(0.0, 1.0, 0.8)), 0.4);
      }

      gl_FragColor = vec4(finalColor, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }
  `
};
