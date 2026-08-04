/**
 * Icon gallery (Iteration 14).
 *
 * A visual catalog of the whole icon collection: categories, names, Russian
 * labels and usage hints. Click an icon to copy its component name
 * (<Icon name="…"/>).
 */
import { useState } from "react";
import { Icon, ICONS, ICON_CATEGORIES } from "../../shared/icons";

export default function IconGalleryPage() {
  const [copied, setCopied] = useState<string | null>(null);

  const copyName = async (name: string) => {
    try {
      await navigator.clipboard.writeText(name);
    } catch {
      // clipboard may be unavailable; fall back to showing the name
    }
    setCopied(name);
    window.setTimeout(() => setCopied(current => current === name ? null : current), 1200);
  };

  return (
    <div className="page-shell icon-gallery-page">
      <div className="page-heading">
        <div>
          <small>ITERATION 14 · ICON COLLECTION</small>
          <h1>Коллекция иконок</h1>
          <p>Набор из {Object.keys(ICONS).length} иконок для всех модулей интерфейса · stroke-стиль, наследуют currentColor · клик — скопировать имя компонента.</p>
        </div>
        <span className="live research">● DEEPUTIN ICONS · {Object.keys(ICONS).length}</span>
      </div>

      {copied && <div className="notice wide">Скопировано: <code>&lt;Icon name="{copied}" /&gt;</code></div>}

      {ICON_CATEGORIES.map(category => {
        const entries = Object.entries(ICONS).filter(([, def]) => def.category === category.key);
        if (!entries.length) return null;
        return (
          <section className="icon-category" key={category.key}>
            <header>
              <span>{category.label}</span>
              <em>{entries.length}</em>
            </header>
            <div className="icon-grid">
              {entries.map(([name, def]) => (
                <button className={`icon-cell ${copied === name ? "copied" : ""}`} key={name} onClick={() => void copyName(name)} title={`<Icon name="${name}" />`}>
                  <span className="icon-preview"><Icon name={name} size={30} /></span>
                  <b>{name}</b>
                  <i>{def.label}</i>
                  <small>{def.hint}</small>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
