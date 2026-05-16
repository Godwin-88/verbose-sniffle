import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getTask } from '@/api/tasks';

export function useQuickAction() {
  const queryClient = useQueryClient();

  const run = async (
    fn: () => Promise<{ task_id: string }>,
    label: string,
    invalidateKeys: string[][] = []
  ) => {
    const toastId = toast.loading(`${label} — starting...`);
    try {
      const { task_id } = await fn();
      toast.loading(`${label} — running`, {
        id: toastId,
        description: `Task ${task_id.slice(0, 8)}…`,
      });

      const poll = setInterval(async () => {
        try {
          const task = await getTask(task_id);
          if (task.status === 'done') {
            clearInterval(poll);
            const result = task.result_json || {};
            const desc =
              result.new !== undefined
                ? `Scraped ${result.scraped} · ${result.new} new`
                : result.processed !== undefined
                ? `Processed ${result.processed} records`
                : undefined;
            toast.success(`${label} complete`, { id: toastId, description: desc });
            queryClient.invalidateQueries({ queryKey: ['stats'] });
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
            for (const key of invalidateKeys) {
              queryClient.invalidateQueries({ queryKey: key });
            }
          } else if (task.status === 'failed') {
            clearInterval(poll);
            toast.error(`${label} failed`, {
              id: toastId,
              description: task.error || 'Unknown error',
            });
          }
        } catch {
          clearInterval(poll);
        }
      }, 3000);
    } catch {
      toast.error(`Failed to start ${label}`, { id: toastId });
    }
  };

  return { run };
}
