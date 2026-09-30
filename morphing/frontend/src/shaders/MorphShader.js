import * as THREE from 'three';

export const MorphShaderMaterialDefinition = {
  uniforms: {
    u_weights: { value: new THREE.Vector4(1, 0, 0, 0) },
    u_textureA: { value: null },
    u_textureB: { value: null },
    u_textureC: { value: null },
    u_textureD: { value: null },
    u_textureDiff: { value: null },
    u_showHeatmap: { value: 0.0 },
    u_showUVDiff: { value: 0.0 },
    u_wireframeMode: { value: 0.0 },
    u_lightDirection: { value: new THREE.Vector3(0.5, 1.0, 1.5).normalize() },
    u_useLighting: { value: 0.0 },
  },

  vertexShader: `
    attribute vec3 positionB;
    attribute vec3 positionC;
    attribute vec3 positionD;
    attribute vec2 uvCoords;

    varying vec2 vUv;
    varying vec3 vNormalVec;
    varying float vDiff;

    uniform vec4 u_weights;

    void main() {
      vUv = uvCoords;
      vec3 morphedPos = position * u_weights.x
        + positionB * u_weights.y
        + positionC * u_weights.z
        + positionD * u_weights.w;
      // Endpoint difference remains a useful and stable heatmap while the
      // timeline itself follows Catmull-Rom weights in u_weights.
      vDiff = length(position - positionD);
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
    uniform sampler2D u_textureC;
    uniform sampler2D u_textureD;
    uniform sampler2D u_textureDiff;
    uniform vec4 u_weights;
    uniform float u_showHeatmap;
    uniform float u_showUVDiff;
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
      vec4 texA = texture2D(u_textureA, vUv);
      vec4 texB = texture2D(u_textureB, vUv);
      vec4 texC = texture2D(u_textureC, vUv);
      vec4 texD = texture2D(u_textureD, vUv);
      vec4 blendedTex = texA * u_weights.x + texB * u_weights.y
        + texC * u_weights.z + texD * u_weights.w;
      // Catmull-Rom can have small negative basis weights; keep texture RGB
      // display-safe while preserving the cubic trajectory of the geometry.
      blendedTex = max(blendedTex, vec4(0.0));

      float diffLight = max(dot(normalize(vNormalVec), u_lightDirection), 0.0);
      vec3 lit = vec3(0.45) + diffLight * vec3(0.55);
      vec3 finalColor = blendedTex.rgb * mix(vec3(1.0), lit, u_useLighting);

      if (u_showUVDiff > 0.5) {
        finalColor = texture2D(u_textureDiff, vUv).rgb;
      }
      if (u_showHeatmap > 0.5) {
        vec3 heat = srgbToLinear(getHeatmapColor(vDiff));
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
