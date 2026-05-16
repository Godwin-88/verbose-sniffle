import { useQuery } from '@tanstack/react-query';
import { getTasks } from '@/api/tasks';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { StatusPill } from '@/components/shared/StatusPill';
import { formatDistanceToNow, differenceInSeconds } from 'date-fns';
import { Zap } from 'lucide-react';

interface Task {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  user_id: string;
  params_json?: any;
  result_json?: any;
  error?: string;
  created_at: string;
  updated_at?: string;
}

function getDuration(task: Task): string {
  if (!task.updated_at || task.status === 'running' || task.status === 'pending') return '—';
  const secs = differenceInSeconds(new Date(task.updated_at + 'Z'), new Date(task.created_at + 'Z'));
  return secs < 60 ? `${secs}s` : `${Math.round(secs / 60)}m ${secs % 60}s`;
}

function getResult(task: Task): string {
  if (!task.result_json) return '—';
  try {
    const r = typeof task.result_json === 'string' ? JSON.parse(task.result_json) : task.result_json;
    if (r.new !== undefined) return `Scraped ${r.scraped} · New ${r.new}`;
    if (r.processed !== undefined) return `Processed ${r.processed}`;
  } catch { /* noop */ }
  return '—';
}

export default function Tasks() {
  const { data: tasks = [], isLoading } = useQuery<Task[]>({
    queryKey: ['tasks'],
    queryFn: getTasks,
    // Poll fast when any task is active, slow otherwise
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasActive = Array.isArray(data) &&
        data.some(t => t.status === 'running' || t.status === 'pending');
      return hasActive ? 3000 : 15000;
    },
  });

  return (
    <div className="space-y-6 pb-10">
      <div className="flex items-center gap-2">
        <Zap className="w-5 h-5 text-indigo-500" />
        <h1 className="text-2xl font-bold">Background Tasks</h1>
        {tasks.some(t => t.status === 'running' || t.status === 'pending') && (
          <span className="inline-flex items-center gap-1.5 text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2.5 py-0.5 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
            Active
          </span>
        )}
      </div>

      <div className="border rounded-lg bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Result</TableHead>
              <TableHead>Error</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                  Loading tasks…
                </TableCell>
              </TableRow>
            ) : tasks.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                  No tasks yet. Use Quick Actions on the Dashboard to start.
                </TableCell>
              </TableRow>
            ) : (
              tasks.map((task) => (
                <TableRow key={task.id} className={task.status === 'failed' ? 'bg-red-50/40' : ''}>
                  <TableCell className="font-medium text-sm">
                    {task.type.replace(/_/g, ' ')}
                  </TableCell>
                  <TableCell>
                    <StatusPill status={task.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm tabular-nums">
                    {formatDistanceToNow(new Date(task.created_at + 'Z'), { addSuffix: true })}
                  </TableCell>
                  <TableCell className="tabular-nums text-sm">
                    {getDuration(task)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {getResult(task)}
                  </TableCell>
                  <TableCell className="text-sm text-red-500 max-w-[200px] truncate" title={task.error}>
                    {task.error || '—'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
