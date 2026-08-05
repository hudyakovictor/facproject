# Контракты данных

## Входной файл

Поддерживаются JPG/JPEG/PNG, валидное имя `YYYY_MM_DD[_N]`. Декодирование: Pillow EXIF transpose → RGB → OpenCV BGR. Неориентированные байты остаются источником SHA-256.

## Stage 1

Критические массивы `reconstruction.npz`: `ldm106_object_normalized (106,3)`, `ldm134_object_normalized (134,3)`, visibility masks, angles `[pitch,yaw,roll]`, alpha coefficients, identity-only arrays. Все numeric arrays finite; несовпадение shapes — hard fail.

Основной индекс `main_timeline.csv`: photo ID, date, sequence, pose bin, angles, source path, date provenance status и quality fields. `main_index.csv` — compatibility alias.

## Stage 2 Record

`Record.ldm106/ldm134` после патча всегда означают primary analysis coordinates = raw object-normalized. Поле `analysis_space` обязательно публикует это явно. Запрещена тихая подстановка иного пространства.

## Pair row

Обязательные поля: pair ID/type, фото/даты, pose bin, three axis gaps, common visibility, calibrated point count, primary metrics, applicability/exclusion reason, quality/expression flags, calibration coverage, FDR p/q, evidence state. NaN сериализуется по единой policy, а не как строка.

## Версионирование

Любое изменение определения координат, порога, masks, schema field или report interpretation повышает schema/config version. Старые и новые rows нельзя объединять без explicit migration.
