# Протокол экспертной проверки результатов

1. Проверить hash quartet и provenance кадра.
2. Проверить дату, source chain и duplicate cluster.
3. Проверить применимость: тот же bin, axis gaps, visibility, quality, expression.
4. Рассмотреть raw image и reconstruction overlay; исключить detector/crop failure.
5. Сопоставить primary raw geometry с secondary descriptors.
6. Проверить calibration coverage и LOPO sensitivity.
7. Искать повторение события в независимом bin/date/source.
8. Для same-day/return проверить альтернативы: неверная дата, источник, компрессия, реконструкция.
9. Записать observation отдельно от interpretation.
10. Сильная формулировка допускается только после независимого reviewer и adjudication.

Минимальная запись reviewer: run ID, photo/pair IDs, artifact hashes, просмотренные изображения, исключённые конфаундеры, решение, confidence, альтернативные объяснения, имя/дата reviewer. Автоматический score не заменяет экспертное заключение.
