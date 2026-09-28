import type { V2BasisKind, V2ReviewState } from '../../api/v2/dto/types';
import { basisLabels, reviewStateLabels } from './review-model';

export function BasisLabel({ value }: { value: V2BasisKind }) {
  return <span className={`review-basis review-basis-${value}`}>{basisLabels[value]}</span>;
}

export function ReviewState({ value }: { value: V2ReviewState }) {
  return (
    <span className={`review-state review-state-${value}`}>
      <span className="review-state-dot" aria-hidden="true" />
      {reviewStateLabels[value]}
    </span>
  );
}
