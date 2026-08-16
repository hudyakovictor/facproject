/**
 * Разбор OBJ-реконструкции Stage 1 для 3D-панелей.
 *
 * Вынесено из компонента: функция чистая, её проверяет тест без рендера.
 */

export interface ParsedMesh {
  positions: Float32Array;
  indices: Uint32Array;
  vertexCount: number;
  triangleCount: number;
}

/**
 * Разбор OBJ. Берутся только `v` и треугольники из `f` — нормали считаются по
 * геометрии, а UV на этой панели не используются: наложение текстуры требует
 * согласованной развёртки, а её корректность здесь не проверить.
 */
export function parseObj(text: string): ParsedMesh {
  const positions: number[] = [];
  const indices: number[] = [];
  for (const line of text.split("\n")) {
    if (line.startsWith("v ")) {
      const parts = line.split(/\s+/);
      positions.push(Number(parts[1]), Number(parts[2]), Number(parts[3]));
    } else if (line.startsWith("f ")) {
      const parts = line.trim().split(/\s+/).slice(1);
      if (parts.length < 3) continue;
      const corner = parts.map((token) => Number(token.split("/")[0]) - 1);
      // Полигоны с более чем тремя вершинами разбиваются веером.
      for (let index = 1; index + 1 < corner.length; index += 1) {
        indices.push(corner[0], corner[index], corner[index + 1]);
      }
    }
  }
  return {
    positions: new Float32Array(positions),
    indices: new Uint32Array(indices),
    vertexCount: positions.length / 3,
    triangleCount: indices.length / 3,
  };
}

