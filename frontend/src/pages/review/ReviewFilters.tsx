import type { V2BasisKind, V2ReviewState } from '../../api/v2/dto/types';
import type { V2Object } from '../../api/v2/domain/types';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Fields';
import { basisLabels, reviewStateLabels } from './review-model';

export interface ReviewFiltersValue {
  reviewState: V2ReviewState | 'all';
  basisKind: V2BasisKind | 'all';
  objectId: number | 'all';
}

export const initialReviewFilters: ReviewFiltersValue = {
  reviewState: 'all',
  basisKind: 'all',
  objectId: 'all',
};

export function ReviewFilters({
  value,
  objects,
  onChange,
}: {
  value: ReviewFiltersValue;
  objects: readonly V2Object[];
  onChange: (value: ReviewFiltersValue) => void;
}) {
  const filtered = value.reviewState !== 'all' || value.basisKind !== 'all' || value.objectId !== 'all';
  return (
    <div className="review-filters" role="group" aria-label="Фильтры очереди проверки">
      <Select
        label="Состояние проверки"
        value={value.reviewState}
        onChange={(event) =>
          onChange({ ...value, reviewState: event.target.value as ReviewFiltersValue['reviewState'] })
        }
        options={[
          { value: 'all', label: 'Все состояния' },
          ...(['pending', 'approved', 'rejected'] as const).map((item) => ({
            value: item,
            label: reviewStateLabels[item],
          })),
        ]}
      />
      <Select
        label="Основание"
        value={value.basisKind}
        onChange={(event) =>
          onChange({ ...value, basisKind: event.target.value as ReviewFiltersValue['basisKind'] })
        }
        options={[
          { value: 'all', label: 'Все основания' },
          ...(['forecast', 'observed_status'] as const).map((item) => ({
            value: item,
            label: basisLabels[item],
          })),
        ]}
      />
      <Select
        label="Объект"
        value={String(value.objectId)}
        onChange={(event) =>
          onChange({
            ...value,
            objectId: event.target.value === 'all' ? 'all' : Number(event.target.value),
          })
        }
        options={[
          { value: 'all', label: 'Все объекты' },
          ...objects.map((object) => ({ value: String(object.objectId), label: object.objectName })),
        ]}
      />
      {filtered && (
        <Button variant="ghost" onClick={() => onChange(initialReviewFilters)}>
          Сбросить фильтры
        </Button>
      )}
    </div>
  );
}
