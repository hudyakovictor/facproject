# Реестр рисков

| Риск | Тяжесть | Контроль |
|---|---:|---|
| Pose leakage доминирует identity | критический | raw + axis gap + same-bin |
| Контаминация calibration | критический | person-balanced, lower80, LOPO |
| Ошибка/конфликт даты | критический | filename authority, EXIF conflict, ledger |
| Correlated frame pairs inflate CI | критический | cluster ESS/bootstrap |
| NaN utility ломает subset/weights | критический | sanitation + exact-count test |
| NULL return false-positive | высокий | absolute divergence + trend corroboration |
| Quality/source-domain confounding | высокий | quality gate, abstention, holdout |
| Profile self-occlusion | высокий | visibility intersection, limited tier |
| Expression geometry | высокий | landmark QC, jaw/smile mismatch review |
| Public overclaim | критический | candidate language + final artifact lint |
| Non-deterministic run | высокий | hash quartet + golden artifacts |
| UI silently renders null as zero | высокий | typed validators + snapshot tests |

## Запреты

Не смешивать схемы/координаты; не менять 9 bin boundaries без нового study; не корректировать дату из EXIF автоматически; не настраивать пороги на основном датасете; не скрывать excluded/failed records; не использовать числа симуляции как доказательство о реальном человеке.
