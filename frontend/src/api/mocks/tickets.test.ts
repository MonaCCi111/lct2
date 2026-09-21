import { afterEach, describe, expect, it } from 'vitest';
import {
  allPredictionFixtures,
  applyTicketState,
  createTicket,
  listTickets,
  resetTicketStore,
  updateTicketStatus,
} from './tickets';
import type { TicketStatus } from '../../domain/ticket/types';

afterEach(resetTicketStore);
const NOW = '2026-09-21T09:00:00Z';

describe('ticket and prediction fixture consistency', () => {
  it('references only predictions that exist', () => {
    const ids = new Set(allPredictionFixtures().map((item) => item.prediction_id));
    for (const ticket of listTickets())
      if (ticket.prediction_id !== null)
        expect({ ticket: ticket.ticket_id, known: ids.has(ticket.prediction_id) }).toEqual({
          ticket: ticket.ticket_id,
          known: true,
        });
  });
  it('gives every prediction with a ticket a resolvable ticket record', () => {
    const tickets = new Map(listTickets().map((item) => [item.ticket_id, item]));
    for (const raw of allPredictionFixtures()) {
      const prediction = applyTicketState(raw);
      if (prediction.ticket_id === null) {
        expect(prediction.review_status).not.toBe('ticket_created');
        continue;
      }
      expect(tickets.has(prediction.ticket_id)).toBe(true);
      expect(prediction.review_status).toBe('ticket_created');
      expect(tickets.get(prediction.ticket_id)?.prediction_id).toBe(prediction.prediction_id);
    }
  });
  it('keeps at most one ticket per prediction', () => {
    const used = listTickets()
      .map((item) => item.prediction_id)
      .filter((id): id is string => id !== null);
    expect(new Set(used).size).toBe(used.length);
  });
  it('copies the stored risk level as priority instead of deriving it', () => {
    const predictions = new Map(allPredictionFixtures().map((item) => [item.prediction_id, item]));
    for (const ticket of listTickets()) {
      if (ticket.prediction_id === null) continue;
      const prediction = predictions.get(ticket.prediction_id)!;
      expect(ticket.priority).toBe(prediction.prediction_supported ? prediction.risk_level : null);
    }
  });
  it('ships a dataset that covers every lifecycle status', () => {
    const counts = listTickets().reduce<Record<string, number>>((acc, item) => {
      acc[item.status] = (acc[item.status] ?? 0) + 1;
      return acc;
    }, {});
    expect(listTickets().length).toBeGreaterThanOrEqual(12);
    for (const status of ['draft', 'approved', 'rejected', 'completed'])
      expect(counts[status] ?? 0).toBeGreaterThanOrEqual(2);
    expect(listTickets().some((item) => item.prediction_id === null)).toBe(true);
    expect(listTickets().some((item) => item.completed_at !== null)).toBe(true);
  });
  it('leaves OW-004 without a ticket so the create flow stays demonstrable', () => {
    expect(listTickets().some((item) => item.prediction_id === 'OW-004')).toBe(false);
  });
});

describe('ticket mock mutations', () => {
  const body = {
    prediction_id: 'OW-004',
    object_id: 203,
    title: 'Проверка датчика',
    description: 'Проверить измерительный тракт и крепление датчика.',
    assignee: 'Смена А',
  };
  it('assigns id, draft status and timestamps on the server side', () => {
    const created = createTicket(body, NOW);
    expect(created.status).toBe('draft');
    expect(created.ticket_id).toMatch(/^WO-2026-\d{4}$/);
    expect({ created: created.created_at, updated: created.updated_at }).toEqual({
      created: NOW,
      updated: NOW,
    });
    expect(created.completed_at).toBeNull();
    // Context is copied from the prediction, priority mirrors its stored risk level.
    expect(created.object_name).toBe('объект Фита');
    expect(created.priority).toBe('critical');
  });
  it('links the created ticket back to its prediction', () => {
    const created = createTicket(body, NOW);
    const prediction = applyTicketState(
      allPredictionFixtures().find((item) => item.prediction_id === 'OW-004')!,
    );
    expect(prediction.ticket_id).toBe(created.ticket_id);
    expect(prediction.review_status).toBe('ticket_created');
  });
  it('rejects a second ticket for the same prediction', () => {
    createTicket(body, NOW);
    expect(() => createTicket(body, NOW)).toThrowError(/уже создан наряд/);
  });
  it('rejects an unknown prediction and invalid field lengths', () => {
    expect(() => createTicket({ ...body, prediction_id: 'NOPE' }, NOW)).toThrowError(/не найден/);
    expect(() => createTicket({ ...body, title: 'ab' }, NOW)).toThrowError(/от 3 до 120/);
    expect(() => createTicket({ ...body, description: 'коротко' }, NOW)).toThrowError(/от 10 до 2000/);
  });
  it('allows a manual ticket without a prediction', () => {
    const created = createTicket({ ...body, prediction_id: null }, NOW);
    expect({ prediction: created.prediction_id, priority: created.priority }).toEqual({
      prediction: null,
      priority: null,
    });
  });
  it.each([
    ['draft', 'approved'],
    ['draft', 'rejected'],
    ['approved', 'completed'],
  ] as const)('allows %s → %s', (from, to) => {
    const ticket = listTickets().find((item) => item.status === from)!;
    const updated = updateTicketStatus(ticket.ticket_id, to, NOW);
    expect(updated.status).toBe(to);
    expect(updated.updated_at).toBe(NOW);
    if (to === 'completed') expect(updated.completed_at).toBe(NOW);
  });
  it.each([
    ['completed', 'draft'],
    ['rejected', 'approved'],
    ['completed', 'rejected'],
    ['draft', 'completed'],
  ] as const)('rejects %s → %s at the API boundary', (from, to) => {
    const ticket = listTickets().find((item) => item.status === from)!;
    expect(() => updateTicketStatus(ticket.ticket_id, to as TicketStatus, NOW)).toThrowError(/недопустим/);
  });
  it('resets deterministically between tests', () => {
    expect(listTickets().some((item) => item.prediction_id === 'OW-004')).toBe(false);
    createTicket(body, NOW);
    expect(listTickets().some((item) => item.prediction_id === 'OW-004')).toBe(true);
    resetTicketStore();
    expect(listTickets().some((item) => item.prediction_id === 'OW-004')).toBe(false);
  });
});
