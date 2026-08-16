import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import type { PhotoInfoKeys } from "../../shared/api/schemas";
import { useSkinZones } from "../../shared/api/queries";
import { artifactCompleteness, dateState, limitations } from "./compactFacts";
import {
  flattenInfo,
  formatLeafValue,
  groupByCategory,
  shortenHash,
} from "./infoKeys";
import styles from "./inspector.module.css";

/**
 * Вкладки инспектора (§10.4): Summary, Geometry, Texture, Provenance,
 * Artifacts, Raw.
 *
 * Каждая вкладка читает `info.json` кадра. Если нужного ключа в нём нет,
 * вкладка пишет, чего именно не хватает, и не показывает пустой блок:
 * отсутствие раздела и отсутствие данных в разделе — разные сообщения.
 */

const TABS = [
  { id: "summary", label: "Сводка" },
  { id: "geometry", label: "Геометрия" },
  { id: "texture", label: "Текстура" },
  { id: "provenance", label: "Провенанс" },
  { id: "artifacts", label: "Артефакты" },
  { id: "raw", label: "Все ключи" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function pick(source: Record<string, unknown>, path: string): unknown {
  let current: unknown = source;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "н/д";
  if (typeof value === "boolean") return value ? "да" : "нет";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (Array.isArray(value)) return value.length === 0 ? "нет" : value.map(String).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Rows({ rows }: { rows: Array<[string, unknown, string?]> }) {
  return (
    <dl className={styles.rows}>
      {rows.map(([label, value, hint]) => (
        <div key={label} className={styles.row}>
          <dt className={styles.rowLabel}>{label}</dt>
          <dd className={styles.rowValue}>
            {text(value)}
            {hint && <span className={styles.rowHint}>{hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function InspectorTabs({ data }: { data: PhotoInfoKeys }) {
  const [tab, setTab] = useState<TabId>("summary");
  const info = data.info as Record<string, unknown>;

  return (
    <section className={styles.panel} aria-label="Подробности кадра">
      <div className={styles.tabBar} role="tablist" aria-label="Разделы инспектора">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`inspector-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`inspector-panel-${item.id}`}
            onClick={() => setTab(item.id)}
            className={styles.tabButton}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`inspector-panel-${tab}`}
        aria-labelledby={`inspector-tab-${tab}`}
        className={styles.tabPanel}
      >
        {tab === "summary" && <SummaryTab data={data} />}
        {tab === "geometry" && <GeometryTab info={info} />}
        {tab === "texture" && <TextureTab data={data} />}
        {tab === "provenance" && <ProvenanceTab info={info} />}
        {tab === "artifacts" && <ArtifactsTab data={data} />}
        {tab === "raw" && <RawTab info={info} />}
      </div>
    </section>
  );
}

function SummaryTab({ data }: { data: PhotoInfoKeys }) {
  const info = data.info as Record<string, unknown>;
  const notes = limitations(data);
  const validation = data.validation as Record<string, unknown>;
  return (
    <>
      <Rows
        rows={[
          ["Идентификатор", data.photo_id],
          ["Дата кадра", pick(info, "date")],
          ["Бин ракурса", pick(info, "pose.pose_bin")],
          ["Статус валидации", pick(validation, "status")],
          ["Версия схемы", pick(info, "schema_version")],
          ["Извлечение", pick(info, "extraction_timestamp")],
        ]}
      />
      <h3 className={styles.subHeading}>Ограничения применимости</h3>
      <ul className={styles.limitList}>
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </>
  );
}

function GeometryTab({ info }: { info: Record<string, unknown> }) {
  const contract = pick(info, "landmark_contract") as Record<string, unknown> | undefined;
  return (
    <>
      <h3 className={styles.subHeading}>Системы координат точек</h3>
      {contract ? (
        <Rows
          rows={[
            ["raw", contract.raw],
            ["aligned", contract.aligned],
            ["chronology", contract.chronology],
          ]}
        />
      ) : (
        <p className={styles.empty}>Stage 1 не записал контракт систем координат.</p>
      )}

      <h3 className={styles.subHeading}>Репроекция</h3>
      <Rows
        rows={[
          ["LDM106 RMSE", pick(info, "reprojection.ldm106_224.rmse"), " px, кроп 224"],
          ["LDM106 p95", pick(info, "reprojection.ldm106_224.p95"), " px"],
          ["LDM106 max", pick(info, "reprojection.ldm106_224.max"), " px"],
          ["LDM134 RMSE", pick(info, "reprojection.ldm134_224.rmse"), " px"],
          ["LDM134 p95", pick(info, "reprojection.ldm134_224.p95"), " px"],
        ]}
      />

      <h3 className={styles.subHeading}>Поза и нормировка</h3>
      <Rows
        rows={[
          ["yaw", pick(info, "pose.yaw"), "°"],
          ["pitch", pick(info, "pose.pitch"), "°"],
          ["roll", pick(info, "pose.roll"), "°"],
          ["канонический yaw", pick(info, "pose.canonical_yaw"), "°"],
          ["нормировка", pick(info, "normalization.method")],
          ["масштаб", pick(info, "normalization.scale")],
        ]}
      />

      <h3 className={styles.subHeading}>Видимость и выражение</h3>
      <Rows
        rows={[
          ["Видимых точек LDM106", pick(info, "chronology.visible_landmarks_106"), " из 106"],
          ["Видимых точек LDM134", pick(info, "chronology.visible_landmarks_134"), " из 134"],
          ["Видимая доля лица", pick(info, "quality_inputs.combined_visible_fraction")],
          ["Магнитуда выражения", pick(info, "chronology.expression_magnitude")],
        ]}
      />

      <p className={styles.warn}>
        Меш кадра в API отдельным эндпоинтом не отдаётся: файл `mesh.obj` доступен
        только как артефакт. Суждения о личности по геометрии одного кадра не
        выносятся ни здесь, ни где-либо ещё в интерфейсе.
      </p>
    </>
  );
}

function TextureTab({ data }: { data: PhotoInfoKeys }) {
  const info = data.info as Record<string, unknown>;
  const texture = data.texture as Record<string, unknown>;
  const zones = useSkinZones(data.photo_id);
  // Словарь статусов задаёт backend (`ZONE_STATUSES`): active | excluded | no_data.
  // Раньше здесь сравнивалось с несуществующим "available", поэтому
  // счётчик всегда показывал 0 из N.
  const measured = (zones.data?.zones ?? []).filter((zone) => zone.status === "active");

  return (
    <>
      <h3 className={styles.subHeading}>Сводка texture.json</h3>
      {Object.keys(texture).length === 0 ? (
        <p className={styles.empty}>Файл texture.json для кадра не создан.</p>
      ) : (
        <Rows
          rows={[
            ["Схема", pick(texture, "schema")],
            ["Модель", pick(texture, "model")],
            ["Источник пикселей", pick(texture, "source")],
            ["Качество", pick(texture, "quality.status") ?? pick(texture, "quality")],
            [
              "Аутентичность",
              pick(texture, "authenticity.status") ?? pick(texture, "authenticity"),
            ],
          ]}
        />
      )}

      <h3 className={styles.subHeading}>Оценки кожи из info.json</h3>
      <Rows
        rows={[
          ["Качество кожи", pick(info, "skin_quality_status")],
          ["Оценка качества", pick(info, "skin_quality_score")],
          ["Аутентичность", pick(info, "skin_authenticity_status")],
          ["Оценка аутентичности", pick(info, "skin_authenticity_score")],
        ]}
      />

      <h3 className={styles.subHeading}>Зоны кожи</h3>
      {zones.isPending && <p className={styles.empty}>Загрузка зон…</p>}
      {zones.isError && (
        <p className={styles.empty}>
          Зоны кожи для кадра недоступны: backend не вернул измерения.
        </p>
      )}
      {zones.data && (
        <>
          <p className={styles.rowHint}>
            Измерено {measured.length} из {zones.data.zone_count} · исключено{" "}
            {zones.data.excluded_zone_count} · без данных {zones.data.no_data_zone_count}.
            Неизмеренная зона — это не нулевое значение.
          </p>
          <ul className={styles.zoneList}>
            {zones.data.zones.map((zone) => {
              const value =
                zone.texture_score ?? zone.quality ?? zone.visible_fraction ?? null;
              return (
                <li
                  key={zone.zone_id ?? zone.name ?? ""}
                  className={styles.zoneItem}
                  data-status={zone.status}
                  title={[
                    zone.zone_id ?? "без zone_id в атласе",
                    zone.name ?? "",
                    zone.group ?? "группа н/д",
                    zone.exclusion_reasons?.length
                      ? `причины: ${zone.exclusion_reasons.join(", ")}`
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                >
                  <span className={styles.zoneName}>{zone.label_ru ?? zone.name ?? ""}</span>
                  <span className={styles.zoneValue}>
                    {zone.status === "active"
                      ? text(value)
                      : zone.status === "excluded"
                        ? "исключена"
                        : "нет данных"}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className={styles.rowHint}>
            Показан texture_score из `quality.json` (если его нет — quality или
            visible_fraction из `skin_zone_quality.json`). Остальные каналы
            (laplacian_var, tenengrad_mean, доли бликов и теней) приходят тем же
            эндпоинтом и видны в подсказке к зоне.
          </p>
          {zones.data.available_sources && (
            <p className={styles.rowHint}>
              Источники на диске: skin_zone_quality{" "}
              {zones.data.available_sources.skin_zone_quality ? "есть" : "нет"} ·
              per_zone_quality{" "}
              {zones.data.available_sources.per_zone_quality ? "есть" : "нет"} · wrinkle_zones{" "}
              {zones.data.available_sources.wrinkle_zones ? "есть" : "нет"}
              {zones.data.available_sources.wrinkle_note
                ? ` · ${zones.data.available_sources.wrinkle_note}`
                : ""}
            </p>
          )}
        </>
      )}
    </>
  );
}

function ProvenanceTab({ info }: { info: Record<string, unknown> }) {
  const dates = dateState(info);
  const digest = pick(info, "source_digest");
  const dhash = pick(info, "perceptual_dhash");
  const duplicate = pick(info, "near_duplicate_of");

  return (
    <>
      <h3 className={styles.subHeading}>Цепочка источника</h3>
      <Rows
        rows={[
          ["Имя файла", pick(info, "source_filename")],
          ["Относительный путь", pick(info, "source_relative_path")],
          ["Статус сайдкара", pick(info, "source_provenance.status")],
          ["Путь сайдкара", pick(info, "source_provenance.sidecar_path")],
          ["Дайджест сайдкара", pick(info, "source_provenance.sidecar_digest")],
        ]}
      />

      <h3 className={styles.subHeading}>Хеши</h3>
      <dl className={styles.rows}>
        <div className={styles.row}>
          <dt className={styles.rowLabel}>SHA-256 источника</dt>
          <dd className={styles.rowValue} title={typeof digest === "string" ? digest : undefined}>
            <span className={styles.mono}>
              {typeof digest === "string" ? shortenHash(digest, 10) : "н/д"}
            </span>
          </dd>
        </div>
        <div className={styles.row}>
          <dt className={styles.rowLabel}>Перцептивный dhash</dt>
          <dd className={styles.rowValue}>
            <span className={styles.mono}>{text(dhash)}</span>
          </dd>
        </div>
        <div className={styles.row}>
          <dt className={styles.rowLabel}>Близкий дубликат</dt>
          <dd className={styles.rowValue}>
            {duplicate === null || duplicate === undefined ? (
              <>
                не найден
                <span className={styles.rowHint}>
                  Stage 1 сравнивает dhash в пределах прогона; за его пределами
                  дубликаты не искались
                </span>
              </>
            ) : (
              text(duplicate)
            )}
          </dd>
        </div>
      </dl>

      <h3 className={styles.subHeading}>Дата</h3>
      <Rows
        rows={[
          ["Авторитет", dates.authority],
          ["Дата из имени файла", pick(info, "date_provenance.filename_date")],
          ["Дата EXIF", dates.exif],
          ["Расхождение, дней", dates.deltaDays],
          ["Конфликтующие источники", dates.conflicts],
        ]}
      />
      {dates.policy && <p className={styles.warn}>{dates.policy}</p>}

      <h3 className={styles.subHeading}>Права</h3>
      <p className={styles.empty}>
        Права на кадр Stage 1 не хранит: они задаются провенанс-сайдкаром и
        редактируются в разделе данных. Здесь показывать нечего.
      </p>

      <h3 className={styles.subHeading}>Версии кода и моделей</h3>
      <Rows
        rows={[
          ["Хеш кода", pick(info, "code_hash")],
          ["Хеш конфигурации", pick(info, "config_hash")],
          ["Хеш модели", pick(info, "model_hash")],
        ]}
      />
    </>
  );
}

function formatBytes(size: number | null): string {
  if (size === null) return "н/д";
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} КБ`;
  return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
}

function ArtifactsTab({ data }: { data: PhotoInfoKeys }) {
  const completeness = artifactCompleteness(data.artifacts ?? []);
  const files = pick(data.info as Record<string, unknown>, "files") as
    | Record<string, unknown>
    | undefined;

  const sizeOf = (name: string): number | null => {
    if (!files) return null;
    const entry = files[name];
    if (typeof entry === "number") return entry;
    if (entry && typeof entry === "object") {
      const size = (entry as Record<string, unknown>).size;
      if (typeof size === "number") return size;
    }
    return null;
  };

  return (
    <>
      <p className={styles.rowHint}>
        Ожидается {completeness.present.length + completeness.missing.length} файлов,
        создано {completeness.present.length}.
      </p>
      <ul className={styles.artifactList}>
        {completeness.present.map((name) => (
          <li key={name} className={styles.artifactItem}>
            <span className={styles.mono}>{name}</span>
            <span className={styles.rowHint}>{formatBytes(sizeOf(name))}</span>
            <a
              className={styles.artifactLink}
              href={`/api/v1/photos/${encodeURIComponent(data.photo_id)}/artifacts/${encodeURIComponent(name)}`}
              download
            >
              <Download className="h-3 w-3" aria-hidden="true" /> скачать
            </a>
          </li>
        ))}
      </ul>

      {completeness.missing.length > 0 && (
        <>
          <h3 className={styles.subHeading}>Не созданы</h3>
          <ul className={styles.artifactList}>
            {completeness.missing.map((name) => (
              <li key={name} className={styles.artifactItem} data-missing="true">
                <span className={styles.mono}>{name}</span>
                <span className={styles.rowHint}>артефакт отсутствует</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {completeness.extra.length > 0 && (
        <>
          <h3 className={styles.subHeading}>Сверх ожидаемого набора</h3>
          <ul className={styles.artifactList}>
            {completeness.extra.map((name) => (
              <li key={name} className={styles.artifactItem}>
                <span className={styles.mono}>{name}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function RawTab({ info }: { info: Record<string, unknown> }) {
  const [filter, setFilter] = useState("");
  const leaves = useMemo(() => flattenInfo(info), [info]);
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return leaves;
    return leaves.filter(
      (leaf) =>
        leaf.path.toLowerCase().includes(needle) ||
        String(leaf.value ?? "").toLowerCase().includes(needle),
    );
  }, [leaves, filter]);
  const groups = useMemo(() => groupByCategory(filtered), [filtered]);

  return (
    <>
      <label className={styles.rawSearch}>
        <Search className="h-3.5 w-3.5" aria-hidden="true" />
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Поиск по ключу или значению"
          aria-label="Поиск по ключам info.json"
        />
        <span className={styles.rowHint}>
          {filtered.length} из {leaves.length}
        </span>
      </label>

      {groups.length === 0 && <p className={styles.empty}>Ничего не найдено.</p>}

      {groups.map((group) => (
        <details key={group.category} open={groups.length <= 2}>
          <summary className={styles.groupSummary}>
            {group.title} · {group.leaves.length}
          </summary>
          <dl className={styles.rows}>
            {group.leaves.map((leaf) => (
              <div key={leaf.path} className={styles.row}>
                <dt className={styles.rowLabel}>
                  <span className={styles.mono}>{leaf.path}</span>
                </dt>
                <dd className={styles.rowValue} data-null={leaf.kind === "null"}>
                  <span className={styles.mono}>
                    {leaf.kind === "string" && String(leaf.value).length > 24
                      ? shortenHash(String(leaf.value), 10)
                      : formatLeafValue(leaf)}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ))}
    </>
  );
}
