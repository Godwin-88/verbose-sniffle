import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type Status =
  | 'pending'
  | 'ready_for_review'
  | 'approved'
  | 'dispatched'
  | 'rejected'
  | 'running'
  | 'done'
  | 'failed';

const statusMap: Record<Status, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-gray-500 hover:bg-gray-600' },
  ready_for_review: { label: 'Ready for Review', className: 'bg-amber-500 hover:bg-amber-600 text-white' },
  approved: { label: 'Approved', className: 'bg-blue-500 hover:bg-blue-600 text-white' },
  dispatched: { label: 'Dispatched', className: 'bg-green-500 hover:bg-green-600 text-white' },
  rejected: { label: 'Rejected', className: 'bg-red-500 hover:bg-red-600 text-white' },
  running: { label: 'Running', className: 'bg-indigo-500 hover:bg-indigo-600 text-white animate-pulse' },
  done: { label: 'Done', className: 'bg-green-500 hover:bg-green-600 text-white' },
  failed: { label: 'Failed', className: 'bg-red-500 hover:bg-red-600 text-white' },
};

export function StatusPill({ status }: { status: Status }) {
  const config = statusMap[status] || statusMap.pending;

  return (
    <Badge className={cn('whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-none border-0', config.className)}>
      {config.label}
    </Badge>
  );
}
