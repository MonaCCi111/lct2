import { setupWorker } from 'msw/browser';
import { v2Handlers } from '../v2/mocks/handlers';
import { handlers } from './handlers';
export const worker = setupWorker(...handlers, ...v2Handlers);
