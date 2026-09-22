import React from 'react';
import type { ProvenanceSource } from '../types';
import { getProvenanceLabel, getProvenanceBadgeClass } from '../presentation';

export interface FieldSourceBadgeProps {
  source: ProvenanceSource;
  label?: string;
  className?: string;
}

export const FieldSourceBadge: React.FC<FieldSourceBadgeProps> = ({
  source,
  label,
  className = '',
}) => {
  const displayLabel = label || getProvenanceLabel(source);
  const badgeClasses = getProvenanceBadgeClass(source);

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${badgeClasses} ${className}`}
      title={`Data source: ${displayLabel}`}
      data-testid={`provenance-badge-${source}`}
    >
      {displayLabel}
    </span>
  );
};

export default FieldSourceBadge;
