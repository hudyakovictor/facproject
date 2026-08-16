import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { POSE_BINS, poseLabel } from "../../shared/poseBins";
import { isFinding } from "../../shared/findings";
import { NAV_ROUTES } from "../../app/navigation";
import styles from "./commandPalette.module.css";

interface Command {
  id: string;
  label: string;
  hint: string;
  group: string;
  run: () => void;
}

/**
 * Командная палитра ⌘K / Ctrl+K по §4.4 ТЗ.
 *
 * Раньше сочетание упоминалось только в подсказке на витрине дизайн-системы.
 * Палитра даёт клавиатурный доступ к навигации, переключению ракурса, режимам
 * и поиску конкретного кадра по идентификатору или дате.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const timeline = useTimeline();
  const store = useAnalysisStore();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const photos = useMemo(() => timeline.data?.photos ?? [], [timeline.data]);

  const commands = useMemo<Command[]>(() => {
    const navigation: Command[] = NAV_ROUTES.map((route) => ({
      id: `nav:${route.to}`,
      label: route.full,
      hint: route.to,
      group: "Переход",
      run: () => void navigate({ to: route.to }),
    }));

    const poses: Command[] = POSE_BINS.map((bin) => ({
      id: `pose:${bin.id}`,
      label: `Ракурс: ${bin.fullLabel}`,
      hint: bin.id,
      group: "Ракурс",
      run: () => {
        store.setActivePose(bin.id);
        store.setMultiPose(false);
      },
    }));

    const findingCount = photos.filter(isFinding).length;
    const modes: Command[] = [
      {
        id: "mode:findings",
        label: store.findingsMode ? "Выключить режим находок" : "Включить режим находок",
        hint: `${findingCount} находок`,
        group: "Режим",
        run: () => store.setFindingsMode(!store.findingsMode),
      },
      {
        id: "mode:multipose",
        label: store.multiPose ? "Показать один ракурс" : "Показать все ракурсы",
        hint: "сравнение пар остаётся внутри бина",
        group: "Режим",
        run: () => store.setMultiPose(!store.multiPose),
      },
      {
        id: "mode:blind",
        label: store.blindMode ? "Выключить слепой режим" : "Включить слепой режим",
        hint: "скрыть идентифицирующие подписи",
        group: "Режим",
        run: () => store.setBlindMode(!store.blindMode),
      },
      {
        id: "mode:clear-pair",
        label: "Сбросить пару A/B",
        hint: store.pairA ?? "пара не выбрана",
        group: "Режим",
        run: () => store.clearPair(),
      },
    ];

    const trimmed = query.trim().toLowerCase();
    const photoMatches: Command[] = trimmed.length >= 2
      ? photos
          .filter(
            (photo) =>
              photo.id.toLowerCase().includes(trimmed) ||
              (photo.date ?? "").toLowerCase().includes(trimmed),
          )
          .slice(0, 8)
          .map((photo) => ({
            id: `photo:${photo.id}`,
            label: `${photo.date ?? "дата н/д"} · ${photo.id}`,
            hint: poseLabel(photo.bucket),
            group: "Кадр",
            run: () => {
              store.setSelectedPhoto(photo.id);
              void navigate({ to: "/timeline" as const });
            },
          }))
      : [];

    return [...photoMatches, ...navigation, ...poses, ...modes];
  }, [navigate, photos, query, store]);

  const filtered = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return commands.slice(0, 12);
    return commands
      .filter(
        (command) =>
          command.label.toLowerCase().includes(trimmed) ||
          command.hint.toLowerCase().includes(trimmed),
      )
      .slice(0, 12);
  }, [commands, query]);

  const runCommand = (command: Command) => {
    command.run();
    setOpen(false);
    setQuery("");
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content} aria-describedby={undefined}>
          <Dialog.Title className={styles.srOnly}>Командная палитра</Dialog.Title>
          <div className={styles.searchRow}>
            <Search className={styles.searchIcon} aria-hidden="true" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && filtered[0]) runCommand(filtered[0]);
              }}
              placeholder="Переход, ракурс, режим, идентификатор кадра…"
              aria-label="Поиск команды"
              className={styles.input}
            />
            <kbd className={styles.kbd}>ESC</kbd>
          </div>

          <ul className={styles.list}>
            {filtered.length === 0 && (
              <li className={styles.empty}>Ничего не найдено по запросу «{query}»</li>
            )}
            {filtered.map((command) => (
              <li key={command.id}>
                <button type="button" className={styles.command} onClick={() => runCommand(command)}>
                  <span className={styles.group}>{command.group}</span>
                  <span className={styles.label}>{command.label}</span>
                  <span className={styles.hint}>{command.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
