CURRENT={'skin-manifest-v1','skin-surface-observations-v1','skin-atlas-projection-v1','skin-quality-v1','skin-features-v1','skin-wrinkles-v1','skin-material-evidence-v1','skin-pair-v1','skin-temporal-v1'}
def require_current(schema):
 if schema not in CURRENT:raise ValueError(f'unsupported schema {schema}; explicit read-only migration required, silent rewrite forbidden')
def migrate(payload,target):
 source=payload.get('schema')
 if source==target:return dict(payload)
 raise NotImplementedError(f'no approved migration {source} -> {target}')
