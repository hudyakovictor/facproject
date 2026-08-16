import { useState, useEffect, useCallback } from 'react';
import type { TimelinePhoto, TimelineResponse } from '../../types/timeline';
import { validateTimelineResponse, logValidationResult, type ValidationResult } from '../dataValidation';

/**
 * Data Logger Panel Component.
 * Displays data validation issues and logs.
 */

interface DataLoggerProps {
  data: TimelineResponse | null;
  photos: TimelinePhoto[];
}

export function DataLogger({ data, photos }: DataLoggerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [filter, setFilter] = useState<'all' | 'error' | 'warning' | 'info'>('all');

  // Run validation when data changes
  useEffect(() => {
    if (data) {
      const result = validateTimelineResponse(data);
      setValidationResult(result);
      logValidationResult(result);
    }
  }, [data]);

  const handleValidate = useCallback(() => {
    if (data) {
      const result = validateTimelineResponse(data);
      setValidationResult(result);
      logValidationResult(result);
    }
  }, [data]);

  if (!validationResult) {
    return null;
  }

  const errors = validationResult.issues.filter(i => i.severity === 'error');
  const warnings = validationResult.issues.filter(i => i.severity === 'warning');
  const infos = validationResult.issues.filter(i => i.severity === 'info');

  const filteredIssues = filter === 'all' 
    ? validationResult.issues 
    : validationResult.issues.filter(i => i.severity === filter);

  return (
    <>
      <button
        className="data-logger-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Data Validation Logger"
      >
        <span className="logger-icon">📋</span>
        {errors.length > 0 && <span className="logger-badge error">{errors.length}</span>}
        {warnings.length > 0 && errors.length === 0 && (
          <span className="logger-badge warning">{warnings.length}</span>
        )}
      </button>

      {isOpen && (
        <div className="data-logger-panel">
          <div className="logger-header">
            <span className="logger-title">DATA VALIDATION LOG</span>
            <div className="logger-filters">
              <button
                className={`logger-filter ${filter === 'all' ? 'active' : ''}`}
                onClick={() => setFilter('all')}
              >
                All ({validationResult.issues.length})
              </button>
              <button
                className={`logger-filter error ${filter === 'error' ? 'active' : ''}`}
                onClick={() => setFilter('error')}
              >
                Errors ({errors.length})
              </button>
              <button
                className={`logger-filter warning ${filter === 'warning' ? 'active' : ''}`}
                onClick={() => setFilter('warning')}
              >
                Warnings ({warnings.length})
              </button>
              <button
                className={`logger-filter info ${filter === 'info' ? 'active' : ''}`}
                onClick={() => setFilter('info')}
              >
                Info ({infos.length})
              </button>
            </div>
            <button className="logger-refresh" onClick={handleValidate}>
              ↻
            </button>
            <button className="logger-close" onClick={() => setIsOpen(false)}>
              ×
            </button>
          </div>

          <div className="logger-summary">
            <span className="logger-summary-item">
              Stage: <strong>{validationResult.stage}</strong>
            </span>
            <span className="logger-summary-item">
              Photos: <strong>{validationResult.totalPhotos}</strong>
            </span>
            <span className="logger-summary-item">
              Schema: <strong className={validationResult.schemaCompliant ? 'ok' : 'error'}>
                {validationResult.schemaCompliant ? 'OK' : 'FAIL'}
              </strong>
            </span>
          </div>

          <div className="logger-content">
            {filteredIssues.length === 0 ? (
              <div className="logger-empty">No issues found</div>
            ) : (
              <div className="logger-issues">
                {filteredIssues.map((issue, index) => (
                  <div key={index} className={`logger-issue logger-issue-${issue.severity}`}>
                    <span className="logger-issue-severity">
                      {issue.severity === 'error' ? '❌' : issue.severity === 'warning' ? '⚠️' : 'ℹ️'}
                    </span>
                    <span className="logger-issue-field">{issue.field}</span>
                    {issue.photoId && (
                      <span className="logger-issue-photo">{issue.photoId.slice(0, 20)}...</span>
                    )}
                    <span className="logger-issue-message">{issue.message}</span>
                    {issue.value !== undefined && (
                      <span className="logger-issue-value">{String(issue.value)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="logger-footer">
            <button
              className="logger-btn"
              onClick={() => {
                if (data) {
                  console.group('[Timeline Data] Full Response');
                  console.log('Schema:', data.schema);
                  console.log('Photos count:', data.photos.length);
                  console.log('Era meta:', data.era_meta);
                  console.log('Chronology anomalies:', data.chronology_anomalies);
                  console.log('UI fields schema:', data.ui_fields_schema);
                  console.log('UI violations:', data.ui_fields_violations_by_field);
                  console.log('Sample photo:', data.photos[0]);
                  console.groupEnd();
                }
              }}
            >
              Log Full Data
            </button>
            <button
              className="logger-btn"
              onClick={() => {
                if (photos.length > 0) {
                  const sample = photos[0]!;
                  console.group('[Timeline Data] Sample Photo Fields');
                  Object.entries(sample).forEach(([key, value]) => {
                    console.log(`${key}:`, value);
                  });
                  console.groupEnd();
                }
              }}
            >
              Log Sample Photo
            </button>
          </div>
        </div>
      )}
    </>
  );
}