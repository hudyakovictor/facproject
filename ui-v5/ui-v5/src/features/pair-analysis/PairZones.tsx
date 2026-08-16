import { useMemo, useState } from "react";
import { useSkinZones } from "../../shared/api/queries";
import type { SkinZones } from "../../shared/api/schemas";

/**
 * Сопоставление зон кожи для пары кадров (концепты 16.08.42 / 06.43.04).
 *
 * Важное ограничение, которое нельзя прятать от пользователя: у backend нет
 * метрик зон на уровне пары. `/pairs/{a}/{b}/metrics` зональных колонок не
 * содержит. Поэтому здесь строится разность двух покадровых измерений
 * Stage 1 (`/photos/{id}/skin_zones`), а не готовая парная метрика.
 *
 * Разность texture_score между двумя снимками зависит от условий съёмки
 * (резкость, свет, разрешение) не меньше, чем от самого лица, поэтому она
 * подписана как разница измерений, а не как изменение кожи.
 *
 * Сопоставимы только зоны, активные в обоих кадрах: если зона закрыта
 * ракурсом хотя бы в одном, разность не считается и не заменяется нулём.
 */

type Zone = SkinZones["zones"][number];

type PairedZone = {
  key: string;
  label: string;
  group: string;
  a: Zone | null;
  b: Zone | null;
  comparable: boolean;
  delta: number | null;
};

function zoneValue(zone: Zone | null): number | null {
  if (!zone) return null;
  return zone.texture_score ?? zone.quality ?? null;
}

function formatValue(value: number | null): string {
  return value == null ? "н/д" : value.toFixed(3);
}

function statusLabel(zone: Zone | null): string {
  if (!zone) return "нет в ответе";
  if (zone.status === "active") return "измерена";
  if (zone.status === "excluded") {
    return zone.exclusion_reasons?.length
      ? `исключена: ${zone.exclusion_reasons.join(", ")}`
      : "исключена";
  }
  return "нет данных";
}

function errorText(error: unknown): string {
  const message = (error as { message?: string } | null)?.message;
  return message ? String(message) : "причина не сообщена";
}

export function PairZones({
  photoA,
  photoB,
  labelA,
  labelB,
}: {
  photoA: string;
  photoB: string;
  labelA: string;
  labelB: string;
}) {
  const a = useSkinZones(photoA);
  const b = useSkinZones(photoB);
  const [group, setGroup] = useState("все");
  const [onlyComparable, setOnlyComparable] = useState(false);

  const paired = useMemo<PairedZone[]>(() => {
    const left = new Map((a.data?.zones ?? []).map((zone) => [zone.name ?? "", zone]));
    const right = new Map((b.data?.zones ?? []).map((zone) => [zone.name ?? "", zone]));
    const names = Array.from(new Set([...left.keys(), ...right.keys()])).sort();
    return names.map((name) => {
      const zoneA = left.get(name) ?? null;
      const zoneB = right.get(name) ?? null;
      const valueA = zoneValue(zoneA);
      const valueB = zoneValue(zoneB);
      const comparable =
        zoneA?.status === "active" &&
        zoneB?.status === "active" &&
        valueA != null &&
        valueB != null;
      return {
        key: name,
        label: zoneA?.label_ru ?? zoneB?.label_ru ?? name,
        group: zoneA?.group ?? zoneB?.group ?? "без группы",
        a: zoneA,
        b: zoneB,
        comparable: Boolean(comparable),
        delta: comparable ? (valueB as number) - (valueA as number) : null,
      };
    });
  }, [a.data, b.data]);

  const groups = useMemo(
    () => ["все", ...Array.from(new Set(paired.map((zone) => zone.group))).sort()],
    [paired],
  );

  const visible = paired
    .filter((zone) => group === "все" || zone.group === group)
    .filter((zone) => !onlyComparable || zone.comparable);

  const comparableCount = paired.filter((zone) => zone.comparable).length;
  const maxAbsDelta = Math.max(
    ...paired.map((zone) => (zone.delta == null ? 0 : Math.abs(zone.delta))),
    1e-6,
  );

  const pending = a.isPending || b.isPending;
  const failure = a.error ?? b.error;

  return (
    <section className="space-y-3 rounded-lg border border-line-default bg-surface-base p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-mono text-xs font-bold uppercase text-cyan-300">
          Зоны кожи: {labelA} → {labelB}
        </h3>
        <div className="flex items-center gap-3 text-xs font-mono text-ink-secondary">
          <label className="flex items-center gap-2">
            группа
            <select
              aria-label="Группа зон"
              value={group}
              onChange={(event) => setGroup(event.target.value)}
              className="rounded border border-line-default bg-surface-overlay px-2 py-1 text-cyan-300"
            >
              {groups.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={onlyComparable}
              onChange={(event) => setOnlyComparable(event.target.checked)}
              className="h-4 w-4 accent-cyan-500"
            />
            только сопоставимые
          </label>
        </div>
      </div>

      {pending && <p className="text-xs text-ink-muted">Загрузка зон…</p>}

      {!pending && failure ? (
        <p className="text-xs text-amber-300">
          Зоны кожи недоступны: {errorText(failure)}. Текстурные артефакты есть только
          у вывода Stage 1; без них сравнение по зонам не строится.
        </p>
      ) : null}

      {!pending && !failure && (
        <>
          <p className="text-xs text-ink-muted">
            Сопоставимо {comparableCount} из {paired.length} зон: разность считается
            только там, где зона измерена в обоих кадрах.
          </p>

          <ul className="space-y-1">
            {visible.map((zone) => {
              const valueA = zoneValue(zone.a);
              const valueB = zoneValue(zone.b);
              const width =
                zone.delta == null ? 0 : (Math.abs(zone.delta) / maxAbsDelta) * 100;
              return (
                <li
                  key={zone.key}
                  className="grid grid-cols-[1fr_auto] items-center gap-2 rounded border border-line-default px-2 py-1 text-xs"
                  title={`A: ${statusLabel(zone.a)} · B: ${statusLabel(zone.b)}`}
                >
                  <div className="min-w-0">
                    <div className="truncate font-mono text-ink-primary">{zone.label}</div>
                    <div className="mt-1 h-1.5 w-full rounded bg-surface-raised">
                      {zone.delta != null && (
                        <div
                          className={`h-1.5 rounded ${
                            zone.delta >= 0 ? "bg-cyan-500" : "bg-amber-500"
                          }`}
                          style={{ width: `${width}%` }}
                        />
                      )}
                    </div>
                  </div>
                  <div className="text-right font-mono">
                    {zone.comparable ? (
                      <>
                        <div className="text-ink-secondary">
                          {formatValue(valueA)} → {formatValue(valueB)}
                        </div>
                        <div className={zone.delta! >= 0 ? "text-cyan-300" : "text-amber-300"}>
                          Δ {zone.delta! >= 0 ? "+" : ""}
                          {zone.delta!.toFixed(3)}
                        </div>
                      </>
                    ) : (
                      <div className="text-ink-muted">
                        не сопоставима · A: {statusLabel(zone.a)} · B: {statusLabel(zone.b)}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          {visible.length === 0 && (
            <p className="text-xs text-ink-muted">
              В выбранной группе нет зон, удовлетворяющих фильтру.
            </p>
          )}

          <p className="text-2xs text-ink-muted">
            Значение зоны — texture_score (при отсутствии — quality) из артефактов Stage 1.
            Парных зональных метрик backend не отдаёт, поэтому показана разность
            двух независимых покадровых измерений. На неё влияют условия съёмки
            (резкость, свет, разрешение), а не только состояние кожи. Это измерение,
            а не вывод.
          </p>
        </>
      )}
    </section>
  );
}
