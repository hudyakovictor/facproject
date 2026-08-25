import type { BlockDefinition } from './contracts';

interface EmptyBlockProps {
  definition: BlockDefinition;
}

export function EmptyBlock({ definition }: EmptyBlockProps) {
  return (
    <section className="placeholder-block" aria-labelledby={`${definition.id}-block-title`}>
      <header className="placeholder-block-header">
        <div>
          <p className="micro-label">Block / {definition.id}</p>
          <h3 id={`${definition.id}-block-title`}>{definition.title}</h3>
        </div>
        <span className="block-state">Empty block</span>
      </header>
      <div className="block-semantic-meta" aria-label="Самостоятельная граница блока">
        <span>Self-contained</span>
      </div>
      <p className="placeholder-purpose">{definition.purpose}</p>
      <div className="empty-message" role="status">
        <span className="status-dot" aria-hidden="true" />
        <span>Данные не подключены. Реализация этого блока выполняется отдельно.</span>
      </div>
      <details className="block-contract">
        <summary>Контракт блока: элементы, ключи, источники, действия и состояния</summary>
        <div className="contract-columns">
          <div>
            <h4>Owned elements</h4>
            <ul>
              {definition.elements.map((element) => (
                <li key={element}>{element}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4>Data keys</h4>
            <ul>
              {definition.keys.map((key) => (
                <li key={key}>
                  <code>{key}</code>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4>Source refs</h4>
            <ul>
              {definition.sourceRefs.map((source) => (
                <li key={source}>
                  <code>{source}</code>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4>Actions and states</h4>
            <ul>
              {[
                ...definition.actions.map((action) => `action: ${action}`),
                ...definition.requiredStates.map((state) => `state: ${state}`),
              ].map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </section>
  );
}
