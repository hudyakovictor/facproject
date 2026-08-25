import { Component, type ReactElement, type ReactNode } from 'react';

import type { BlockDefinition, PageDefinition, ResourceState } from './contracts';
import { EmptyBlock } from './PlaceholderBlock';

interface PageBlueprintProps {
  definition: PageDefinition;
  resourceState?: ResourceState;
  renderBlock?: (definition: BlockDefinition) => ReactElement | null;
}

interface BlockErrorBoundaryProps {
  blockTitle: string;
  children: ReactNode;
}

interface BlockErrorBoundaryState {
  hasError: boolean;
}

class BlockErrorBoundary extends Component<BlockErrorBoundaryProps, BlockErrorBoundaryState> {
  state: BlockErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): BlockErrorBoundaryState {
    return { hasError: true };
  }

  handleReload = () => {
    if (typeof window !== 'undefined') window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <section className="block-runtime-error" role="alert">
          <span className="micro-label">Block render error</span>
          <h3>{this.props.blockTitle}</h3>
          <p>
            The block could not render. Source data was not replaced with fallback values; reload or
            inspect the source endpoint before continuing.
          </p>
          <button type="button" onClick={this.handleReload}>
            Reload block
          </button>
        </section>
      );
    }

    return this.props.children;
  }
}

const resourceLabels: Record<ResourceState, string> = {
  loading: 'Loading',
  ready: 'Source connected',
  empty: 'Empty source',
  limited: 'Limited source',
  unavailable: 'Unavailable',
  error: 'Source error',
  stale: 'Stale source',
  missing: 'Missing source',
};

export function PageBlueprint({ definition, resourceState, renderBlock }: PageBlueprintProps) {
  return (
    <div className="page-blueprint">
      <section className="page-blueprint-intro" aria-labelledby={`${definition.id}-page-title`}>
        <div>
          <p className="micro-label">Page blueprint / {definition.id}</p>
          <h2 id={`${definition.id}-page-title`}>{definition.title}</h2>
          <p>{definition.purpose}</p>
        </div>
        <div className="primary-question">
          <span className="micro-label">Primary question</span>
          <strong>{definition.primaryQuestion}</strong>
        </div>
      </section>

      <div className="blueprint-state" role="status">
        <span className="micro-label">Resource state</span>
        <strong>
          {resourceState ? resourceLabels[resourceState] : 'Block-scoped source state'}
        </strong>
        <span>
          Источник запрашивается внутри соответствующего блока. Без ответа API значения не
          показываются.
        </span>
      </div>

      <div className="page-block-list">
        {definition.blocks.map((block) => (
          <div key={block.id}>
            {renderBlock ? (
              <BlockErrorBoundary blockTitle={block.title}>{renderBlock(block)}</BlockErrorBoundary>
            ) : (
              <EmptyBlock definition={block} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
