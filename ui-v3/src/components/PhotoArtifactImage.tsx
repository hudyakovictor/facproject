import { useEffect, useState } from "react";
import { photoImageUrl } from "../lib/api";
import type { PhotoImageKind } from "../lib/types";
import { cx } from "./ui";
export default function PhotoArtifactImage({ photoId, kind = "original", alt, className, cover = false, decorative = false }: {
  photoId: string; kind?: PhotoImageKind; alt?: string; className?: string; cover?: boolean; decorative?: boolean;
}) {
  const [state, setState] = useState<"loading" | "loaded" | "error">("loading");
  const src = photoImageUrl(photoId, kind);
  useEffect(() => { setState("loading"); }, [src]);
  return (
    <div className={cx("artifact", cover && "cover", className)}>
      {state !== "error" && (
        <img src={src} alt={decorative ? "" : (alt || `${kind} ${photoId}`)} loading="lazy" decoding="async"
          style={{ opacity: state === "loaded" ? 1 : 0 }} onLoad={() => setState("loaded")} onError={() => setState("error")} />
      )}
      {state === "loading" && <div className="ph">загрузка {kind}…</div>}
      {state === "error" && <div className="ph bad" role="status">артефакт недоступен<div style={{ marginTop: 4 }}>{kind}</div></div>}
    </div>
  );
}
