export type TicketStatus = 'draft' | 'approved' | 'rejected' | 'completed';
export interface Ticket {
  id: string;
  predictionId: string;
  title: string;
  status: TicketStatus;
  createdAt: string;
}
