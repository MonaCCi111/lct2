import { getSensorTypeLabel } from '../../utils/sensor-type';

/**
 * Shows the sensor type compactly in dense registries. Long domain values get a shorter display
 * label, and the original value always stays available through the title attribute.
 */
export function SensorTypeCell({ sensorType }: { sensorType: string }) {
  return (
    <span className="truncate" title={sensorType}>
      {getSensorTypeLabel(sensorType)}
    </span>
  );
}
