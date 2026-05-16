import { Progress } from '@/components/ui/progress';

export function MatchBar({ score }: { score?: number }) {
  if (score === undefined) return null;

  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <Progress value={score} className="h-2 flex-1" />
      <span className="text-xs font-medium tabular-nums">{score}%</span>
    </div>
  );
}
