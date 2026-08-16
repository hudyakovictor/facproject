/**
 * Разбор имени файла перед загрузкой (§7.1–7.2 ТЗ).
 *
 * Backend принимает только имена вида `YYYY_MM_DD[_N].ext` (`app6/AGENTS.md`)
 * и отвергает остальные. Проверять это до отправки нужно, чтобы оператор
 * увидел причину сразу, а не после загрузки десяти файлов.
 *
 * Главное правило раздела: **дату нельзя исправлять молча**. Разбор здесь
 * ничего не «чинит» — он показывает, что прочитал, и если имя не соответствует
 * формату, требует переименования вручную. Автоматически подставленная дата
 * стала бы утверждением о времени съёмки, которого никто не делал.
 */

export interface ParsedName {
  filename: string;
  /** Дата, прочитанная из имени файла. */
  date: string | null;
  /** Порядковый номер в пределах дня. */
  sequence: number | null;
  extension: string;
  /** Предлагаемый идентификатор кадра. */
  proposedId: string | null;
  /** Причины, по которым файл не будет принят. */
  problems: string[];
}

const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"];
const NAME_PATTERN = /^(\d{4})_(\d{2})_(\d{2})(?:_(\d+))?$/;

/** Существует ли такая календарная дата (31 февраля не существует). */
function isRealDate(year: number, month: number, day: number): boolean {
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function parseFilename(filename: string, now: Date = new Date()): ParsedName {
  const problems: string[] = [];
  const dot = filename.lastIndexOf(".");
  const extension = dot >= 0 ? filename.slice(dot).toLowerCase() : "";
  const stem = dot >= 0 ? filename.slice(0, dot) : filename;

  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    problems.push(
      `расширение ${extension || "отсутствует"} не поддерживается (нужно .jpg, .jpeg или .png)`,
    );
  }

  const match = NAME_PATTERN.exec(stem);
  if (!match) {
    problems.push(
      "имя не соответствует формату ГГГГ_ММ_ДД[_N]: дата будет неизвестна, переименуйте файл вручную",
    );
    return { filename, date: null, sequence: null, extension, proposedId: null, problems };
  }

  const [, y, m, d, seq] = match;
  const year = Number(y);
  const month = Number(m);
  const day = Number(d);

  if (!isRealDate(year, month, day)) {
    problems.push(`даты ${y}-${m}-${d} не существует в календаре`);
    return { filename, date: null, sequence: null, extension, proposedId: null, problems };
  }

  const date = `${y}-${m}-${d}`;
  const parsed = Date.UTC(year, month - 1, day);

  if (parsed > now.getTime()) {
    problems.push("дата в будущем");
  }
  if (year < 1900) {
    problems.push("дата раньше 1900 года");
  }

  return {
    filename,
    date,
    sequence: seq === undefined ? null : Number(seq),
    extension,
    proposedId: `${y}_${m}_${d}${seq === undefined ? "" : `_${seq}`}`,
    problems,
  };
}

/** Файл можно отправлять на сервер. */
export function isAcceptable(parsed: ParsedName): boolean {
  return parsed.problems.length === 0;
}
