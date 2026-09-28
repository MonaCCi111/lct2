import type { CreateTicketRequestDto, TicketDto } from '../dto/ticket';
import type { PredictionDto } from '../dto/prediction';
import type { TicketStatus } from '../../domain/ticket/types';
import { isAllowedTicketTransition } from '../../domain/ticket/types';
import { predictionFixtures } from './fixtures';
import { operationalPredictions } from './operational';
import { objectWorkspacePredictions } from './object-workspace';

export const allPredictionFixtures = (): PredictionDto[] => [
  ...predictionFixtures,
  ...operationalPredictions,
  ...objectWorkspacePredictions,
];
const findPrediction = (id: string) =>
  allPredictionFixtures().find((item) => item.prediction_id === id) ?? null;

type TicketSeed = [
  ticketId: string,
  predictionId: string | null,
  status: TicketStatus,
  assignee: string | null,
  title: string,
  description: string,
  createdAt: string,
  updatedAt: string,
  completedAt: string | null,
];

// Object and sensor context is copied from the source prediction, so a ticket can never point at
// a prediction that does not exist. Manual tickets carry their object explicitly.
const ticketSeeds: TicketSeed[] = [
  [
    'WO-2026-0917',
    'HYDRO-003',
    'draft',
    'Инженер КИП',
    'Проверка дренажного насоса № 2',
    'Повышенная частота пусков и рост тока при той же подаче. Проверить состояние подшипникового узла и режим работы насоса.',
    '2026-09-20T09:10:00Z',
    '2026-09-20T09:10:00Z',
    null,
  ],
  // OW-004 intentionally has no ticket: it is the demo prediction for the create flow.
  [
    'WO-2026-0921',
    'OW-009',
    'draft',
    null,
    'Проверка: Температура подшипника Н-1',
    'Высокий риск по температуре подшипникового узла. Проверить измерительный тракт и крепление датчика, при подтверждении — заменить термопару.',
    '2026-09-20T10:05:00Z',
    '2026-09-20T12:40:00Z',
    null,
  ],
  [
    'WO-2026-0922',
    'OW-005',
    'draft',
    'Электротехническая группа',
    'Проверка: Фаза B · тяговый ввод',
    'Кратковременные просадки фазы B под нагрузкой и дребезг сигнала состояния ввода. Проверить силовые контакты ввода.',
    '2026-09-20T10:32:00Z',
    '2026-09-20T13:05:00Z',
    null,
  ],
  [
    'WO-2026-0923',
    'OP-004',
    'draft',
    'Смена А',
    'Проверка: Дым · кабельный отсек',
    'Критический прогноз по каналу дымового извещателя. Провести чистку и функциональную проверку извещателя по регламенту ТО.',
    '2026-09-20T11:14:00Z',
    '2026-09-20T11:14:00Z',
    null,
  ],
  [
    'WO-2026-0918',
    'OW-016',
    'approved',
    'Служба вентиляции',
    'Проверка: Газ CO · венткамера ВК-6',
    'Устойчивый рост концентрации CO в венткамере. Проверить работу приточной вентиляции и выполнить калибровку газоанализатора.',
    '2026-09-19T14:20:00Z',
    '2026-09-20T08:15:00Z',
    null,
  ],
  [
    'WO-2026-0919',
    'OP-006',
    'approved',
    'Электротехническая группа',
    'Проверка: ИБП · выходная фаза A',
    'Высокий риск по выходной фазе ИБП. Проверить контактные соединения и снять термограмму под нагрузкой.',
    '2026-09-19T16:45:00Z',
    '2026-09-20T07:30:00Z',
    null,
  ],
  [
    'WO-2026-0920',
    'OW-014',
    'approved',
    'Смена Б',
    'Проверка: Фаза C · резервный ввод',
    'Асимметрия фазных напряжений выше порога на резервном вводе. Выполнить протяжку клемм и контрольный замер.',
    '2026-09-19T18:02:00Z',
    '2026-09-20T09:48:00Z',
    null,
  ],
  [
    'WO-2026-0910',
    'OP-013',
    'rejected',
    'Смена А',
    'Проверка: Газ CO · сервисная галерея',
    'Прогноз отклонён диспетчером: канал выведен в ремонт по отдельной заявке, повторная проверка не требуется.',
    '2026-09-18T11:00:00Z',
    '2026-09-19T09:20:00Z',
    null,
  ],
  [
    'WO-2026-0911',
    'OW-012',
    'rejected',
    null,
    'Проверка: Пожарный извещатель ИП-14',
    'Прогноз отклонён: извещатель заменён в ходе планового обслуживания до формирования наряда.',
    '2026-09-18T13:35:00Z',
    '2026-09-18T17:10:00Z',
    null,
  ],
  [
    'WO-2026-0901',
    'OP-003',
    'completed',
    'Смена Б',
    'Проверка: Насос дренажа Н-2',
    'Критический прогноз по дренажному насосу. Выполнена ревизия подшипникового узла, режим работы восстановлен.',
    '2026-09-17T08:40:00Z',
    '2026-09-18T15:05:00Z',
    '2026-09-18T15:05:00Z',
  ],
  [
    'WO-2026-0902',
    'OW-021',
    'completed',
    'Смена А',
    'Проверка: Насос охлаждения Н-3',
    'Рост потребляемого тока при той же подаче. Выполнена чистка контура, параметры вернулись в норму.',
    '2026-09-17T12:15:00Z',
    '2026-09-19T10:25:00Z',
    '2026-09-19T10:25:00Z',
  ],
  [
    'WO-2026-0903',
    'OP-011',
    'completed',
    'Электротехническая группа',
    'Проверка: Фаза C · резервный ввод',
    'Проведена протяжка клемм резервного ввода, асимметрия фазных напряжений устранена.',
    '2026-09-16T09:05:00Z',
    '2026-09-18T11:40:00Z',
    '2026-09-18T11:40:00Z',
  ],
  [
    'WO-2026-0904',
    null,
    'completed',
    'Служба вентиляции',
    'Плановая ревизия вентиляционной установки',
    'Ручной наряд: плановая ревизия приточной установки по графику ТО, вне предиктивного контура.',
    '2026-09-16T07:30:00Z',
    '2026-09-17T16:20:00Z',
    '2026-09-17T16:20:00Z',
  ],
  [
    'WO-2026-0912',
    null,
    'draft',
    null,
    'Осмотр кабельной галереи после ремонта',
    'Ручной наряд: контрольный осмотр кабельной галереи после завершения ремонтных работ подрядчиком.',
    '2026-09-20T08:05:00Z',
    '2026-09-20T08:05:00Z',
    null,
  ],
  [
    'WO-2026-0913',
    null,
    'approved',
    'Смена Б',
    'Замена светильников в щитовой',
    'Ручной наряд: замена вышедших из строя светильников в помещении щитовой освещения.',
    '2026-09-19T10:40:00Z',
    '2026-09-20T06:55:00Z',
    null,
  ],
];

const MANUAL_OBJECT_ID = 203;
const MANUAL_OBJECT_NAME = 'объект Фита';

function buildTicket(seed: TicketSeed): TicketDto {
  const [ticketId, predictionId, status, assignee, title, description, createdAt, updatedAt, completedAt] =
    seed;
  const prediction = predictionId === null ? null : findPrediction(predictionId);
  if (predictionId !== null && prediction === null)
    throw new Error(`Ticket fixture ${ticketId} references unknown prediction ${predictionId}`);
  return {
    ticket_id: ticketId,
    prediction_id: predictionId,
    object_id: prediction?.object_id ?? MANUAL_OBJECT_ID,
    object_name: prediction?.object_name ?? MANUAL_OBJECT_NAME,
    sensor_name: prediction?.sensor_name ?? null,
    piket: prediction?.piket ?? null,
    title,
    description,
    status,
    // Priority mirrors the stored risk level of the source prediction, nothing is derived.
    priority: prediction ? (prediction.prediction_supported ? prediction.risk_level : null) : null,
    assignee,
    created_at: createdAt,
    updated_at: updatedAt,
    completed_at: completedAt,
  };
}

let tickets: TicketDto[] = ticketSeeds.map(buildTicket);
let sequence = 0;

/** Deterministic reset for tests and for every fresh page load. */
export function resetTicketStore() {
  tickets = ticketSeeds.map(buildTicket);
  sequence = 0;
}
export const listTickets = (): TicketDto[] => tickets.map((item) => ({ ...item }));
export const findTicket = (ticketId: string) => tickets.find((item) => item.ticket_id === ticketId) ?? null;
export const findTicketByPrediction = (predictionId: string) =>
  tickets.find((item) => item.prediction_id === predictionId) ?? null;

export class TicketMockError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export function createTicket(body: CreateTicketRequestDto, now: string): TicketDto {
  const title = body.title?.trim() ?? '';
  const description = body.description?.trim() ?? '';
  if (title.length < 3 || title.length > 120)
    throw new TicketMockError('Название должно содержать от 3 до 120 символов.', 422);
  if (description.length < 10 || description.length > 2000)
    throw new TicketMockError('Описание должно содержать от 10 до 2000 символов.', 422);

  let prediction: PredictionDto | null = null;
  if (body.prediction_id !== null) {
    prediction = findPrediction(body.prediction_id);
    if (prediction === null) throw new TicketMockError('Прогноз с указанным идентификатором не найден.', 404);
    // One prediction carries at most one ticket in the current contract.
    const existing = findTicketByPrediction(body.prediction_id);
    if (existing !== null)
      throw new TicketMockError(`Для прогноза уже создан наряд ${existing.ticket_id}.`, 409);
  }

  sequence += 1;
  const ticket: TicketDto = {
    ticket_id: `WO-2026-${String(930 + sequence).padStart(4, '0')}`,
    prediction_id: body.prediction_id,
    object_id: prediction?.object_id ?? body.object_id,
    object_name: prediction?.object_name ?? MANUAL_OBJECT_NAME,
    sensor_name: prediction?.sensor_name ?? null,
    piket: prediction?.piket ?? null,
    title,
    description,
    // Lifecycle status is assigned by the backend, never sent by the client.
    status: 'draft',
    priority: prediction ? (prediction.prediction_supported ? prediction.risk_level : null) : null,
    assignee: body.assignee,
    created_at: now,
    updated_at: now,
    completed_at: null,
  };
  tickets = [ticket, ...tickets];
  return { ...ticket };
}

export function updateTicketStatus(ticketId: string, status: TicketStatus, now: string): TicketDto {
  const ticket = findTicket(ticketId);
  if (ticket === null) throw new TicketMockError('Наряд не найден.', 404);
  // The transition rule is enforced here, not only by disabled buttons in the interface.
  if (!isAllowedTicketTransition(ticket.status, status))
    throw new TicketMockError(`Переход «${ticket.status}» → «${status}» недопустим.`, 409);
  const updated: TicketDto = {
    ...ticket,
    status,
    updated_at: now,
    completed_at: status === 'completed' ? now : ticket.completed_at,
  };
  tickets = tickets.map((item) => (item.ticket_id === ticketId ? updated : item));
  return { ...updated };
}

/**
 * Predictions do not store their ticket themselves: the ticket store is the single source of
 * truth, so every served prediction gets its ticket reference applied here.
 */
export function applyTicketState(prediction: PredictionDto): PredictionDto {
  const ticket = findTicketByPrediction(prediction.prediction_id);
  if (ticket === null) return prediction;
  return { ...prediction, ticket_id: ticket.ticket_id, review_status: 'ticket_created' };
}
export const applyTicketStateToAll = (predictions: readonly PredictionDto[]) =>
  predictions.map(applyTicketState);
