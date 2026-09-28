import type { ModelDomain } from '../domain/prediction/types';
const labels: Record<ModelDomain, string> = {
  POWER_PHASE: 'Электропитание',
  ANALOG_TEMP: 'Температура',
  ANALOG_GAS: 'Газ',
  FIRE_SAFETY: 'Пожарная безопасность',
  HYDRO_MECHANICS: 'Гидромеханика',
};
export const getModelDomainLabel = (domain: ModelDomain) => labels[domain];
