import type { Prediction } from '../../domain/prediction/types';
import { getRiskLabel } from '../../utils/formatters';

export interface TicketFormValues {
  title: string;
  description: string;
  assignee: string;
  objectId: string;
}
export const emptyTicketForm: TicketFormValues = {
  title: '',
  description: '',
  assignee: '',
  objectId: '',
};

export const TITLE_MIN = 3;
export const TITLE_MAX = 120;
export const DESCRIPTION_MIN = 10;
export const DESCRIPTION_MAX = 2000;

export interface TicketFormErrors {
  title?: string;
  description?: string;
  objectId?: string;
}
export function validateTicketForm(values: TicketFormValues, requireObject: boolean): TicketFormErrors {
  const errors: TicketFormErrors = {};
  const title = values.title.trim();
  const description = values.description.trim();
  if (title === '') errors.title = 'Укажите название наряда.';
  else if (title.length < TITLE_MIN || title.length > TITLE_MAX)
    errors.title = `Название должно содержать от ${TITLE_MIN} до ${TITLE_MAX} символов.`;
  if (description === '') errors.description = 'Опишите работы по наряду.';
  else if (description.length < DESCRIPTION_MIN || description.length > DESCRIPTION_MAX)
    errors.description = `Описание должно содержать от ${DESCRIPTION_MIN} до ${DESCRIPTION_MAX} символов.`;
  if (requireObject && values.objectId === '') errors.objectId = 'Выберите объект.';
  return errors;
}
export const hasFormErrors = (errors: TicketFormErrors) => Object.keys(errors).length > 0;

/**
 * Prefills the form from the prediction. The description reuses the recommendation the model
 * already produced — no new recommendation text is generated here.
 */
export function prefillFromPrediction(prediction: Prediction): TicketFormValues {
  const risk = prediction.predictionSupported && prediction.riskLevel !== null;
  const opening = risk
    ? `${getRiskLabel(prediction.riskLevel)} прогноз для датчика ${prediction.sensorName}.`
    : `Прогноз для датчика ${prediction.sensorName}.`;
  const location = [prediction.objectName, prediction.piket].filter(Boolean).join(' · ');
  const recommendation = prediction.recommendation
    ? `\n\nРекомендуемое действие:\n${prediction.recommendation}`
    : '';
  return {
    title: `Проверка: ${prediction.sensorName}`.slice(0, TITLE_MAX),
    description: `${opening}\nРасположение: ${location}.${recommendation}`,
    assignee: '',
    objectId: String(prediction.objectId),
  };
}
