import { HelpCircle } from 'lucide-react';
import { Tooltip } from '../ui/Tooltip';
import { UrgencyIndicator } from '../ui/Badge';
import type { MaintenanceUrgency } from '../../domain/prediction/types';

const steps: MaintenanceUrgency[] = ['FLASH_1_6H', 'URGENT_6_24H', 'PLANNED_24_48H'];

/**
 * Explains the square notation once, in the column header, instead of repeating a legend in every
 * table row. The trigger is a real button so mouse, keyboard and screen-reader users all reach it.
 */
export function UrgencyColumnHint() {
  return (
    <Tooltip
      content={
        <div className="column-hint-content">
          <span>Срочность обслуживания:</span>
          {steps.map((urgency) => (
            <span className="column-hint-row" key={urgency}>
              <UrgencyIndicator value={urgency} />
            </span>
          ))}
        </div>
      }
    >
      <button type="button" className="column-hint" aria-label="Как читать индикатор срочности">
        <HelpCircle size={13} aria-hidden="true" />
      </button>
    </Tooltip>
  );
}
