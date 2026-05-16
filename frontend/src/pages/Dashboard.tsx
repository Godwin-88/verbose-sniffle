import { useQuery } from '@tanstack/react-query';
import { getStats } from '@/api/stats';
import { getTasks } from '@/api/tasks';
import { scrapeJobs, generateJobDocs } from '@/api/jobs';
import { scrapeScholarships, generateScholarshipDocs } from '@/api/scholarships';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { StatusPill } from '@/components/shared/StatusPill';
import { useQuickAction } from '@/hooks/useQuickAction';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow, differenceInSeconds } from 'date-fns';
import { Database, FileText, Zap } from 'lucide-react';

// ─── Pipeline funnel ─────────────────────────────────────────────────────────
const STATUSES = ['pending', 'ready_for_review', 'approved', 'dispatched', 'rejected'] as const;
const STATUS_COLORS: Record<string, string> = {
  pending:          'bg-gray-400',
  ready_for_review: 'bg-amber-500',
  approved:         'bg-blue-500',
  dispatched:       'bg-green-500',
  rejected:         'bg-red-500',
};

function PipelineFunnel({
  title, stats, onSegmentClick,
}: {
  title: string;
  stats: Record<string, number>;
  onSegmentClick: (s: string) => void;
}) {
  const total = STATUSES.reduce((acc, s) => acc + (stats[s] || 0), 0);
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0 space-y-3">
        <div className="h-7 w-full flex rounded-full overflow-hidden bg-muted gap-px">
          {STATUSES.map((s) => {
            const val = stats[s] || 0;
            if (val === 0) return null;
            const width = total > 0 ? (val / total) * 100 : 0;
            return (
              <div
                key={s}
                className={`${STATUS_COLORS[s]} h-full transition-all cursor-pointer hover:brightness-110 first:rounded-l-full last:rounded-r-full`}
                style={{ width: `${width}%` }}
                onClick={() => onSegmentClick(s)}
                title={`${s.replace(/_/g, ' ')}: ${val}`}
              />
            );
          })}
          {total === 0 && <div className="flex-1 bg-muted" />}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              className="flex items-center gap-1.5 text-[10px] text-muted-foreground uppercase tracking-widest font-semibold hover:text-foreground transition-colors"
              onClick={() => onSegmentClick(s)}
            >
              <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[s]}`} />
              {s.replace(/_/g, ' ')} ({stats[s] || 0})
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Stat card ───────────────────────────────────────────────────────────────
function StatCard({ label, value, onClick }: { label: string; value: number; onClick?: () => void }) {
  return (
    <Card
      className={onClick ? 'cursor-pointer hover:border-primary/50 transition-colors' : ''}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
        <p className="text-3xl font-bold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}

// ─── Task result parser ───────────────────────────────────────────────────────
function parseTaskResult(task: any): string {
  if (!task.result_json) return '';
  try {
    const r = typeof task.result_json === 'string' ? JSON.parse(task.result_json) : task.result_json;
    if (r.new !== undefined) return `${r.scraped} scraped · ${r.new} new`;
    if (r.processed !== undefined) return `${r.processed} processed`;
    return '';
  } catch { return ''; }
}

function taskDuration(task: any): string {
  if (!task.updated_at || task.status === 'running' || task.status === 'pending') return '';
  const secs = differenceInSeconds(new Date(task.updated_at + 'Z'), new Date(task.created_at + 'Z'));
  return secs < 60 ? `${secs}s` : `${Math.round(secs / 60)}m`;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const { run } = useQuickAction();

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
    refetchInterval: (data: any) => {
      const active = (data?.state?.data || []).some(
        (t: any) => t.status === 'running' || t.status === 'pending'
      );
      return active ? 3000 : 15000;
    },
  });

  const scrapeWithSettings = (fn: Function, label: string, invalidate: string[][]) => {
    const keywords = (localStorage.getItem('jh_settings_keywords') || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    const sources = JSON.parse(localStorage.getItem('jh_settings_sources') || '[]');
    run(
      () => fn({ keywords: keywords.length ? keywords : undefined, sources: sources.length ? sources : undefined }),
      label,
      invalidate
    );
  };

  const statCards = [
    { label: 'Jobs Pending',       value: stats?.jobs?.pending || 0,                           nav: '/jobs?status=pending' },
    { label: 'Jobs Ready',         value: stats?.jobs?.ready_for_review || 0,                  nav: '/jobs?status=ready_for_review' },
    { label: 'Jobs Approved',      value: stats?.jobs?.approved || 0,                          nav: '/jobs?status=approved' },
    { label: 'Scholarships Ready', value: stats?.scholarships?.ready_for_review || 0,          nav: '/scholarships?status=ready_for_review' },
    { label: 'Fully Funded',       value: stats?.scholarships_by_funding?.fully_funded || 0,   nav: '/scholarships?status=ready_for_review&funding_type=fully_funded' },
    { label: 'Total Dispatched',   value: (stats?.jobs?.dispatched || 0) + (stats?.scholarships?.dispatched || 0), nav: undefined },
  ];

  return (
    <div className="space-y-8 pb-10">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map((s) => (
          <StatCard
            key={s.label}
            label={s.label}
            value={s.value}
            onClick={s.nav ? () => navigate(s.nav!) : undefined}
          />
        ))}
      </div>

      {/* Pipeline funnels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <PipelineFunnel
          title="Jobs Pipeline"
          stats={stats?.jobs || {}}
          onSegmentClick={(s) => navigate(`/jobs?status=${s}`)}
        />
        <PipelineFunnel
          title="Scholarships Pipeline"
          stats={stats?.scholarships || {}}
          onSegmentClick={(s) => navigate(`/scholarships?status=${s}`)}
        />
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => scrapeWithSettings(scrapeJobs, 'Scrape Jobs', [['jobs']])}
          >
            <Database className="w-4 h-4 mr-2" /> Scrape Jobs
          </Button>
          <Button
            variant="outline"
            onClick={() => scrapeWithSettings(scrapeScholarships, 'Scrape Scholarships', [['scholarships']])}
          >
            <Database className="w-4 h-4 mr-2" /> Scrape Scholarships
          </Button>
          <Button onClick={() => run(() => generateJobDocs({}), 'Generate Job Docs', [['jobs']])}>
            <FileText className="w-4 h-4 mr-2" /> Generate Job Docs
          </Button>
          <Button onClick={() => run(() => generateScholarshipDocs({}), 'Generate Scholarship Docs', [['scholarships']])}>
            <FileText className="w-4 h-4 mr-2" /> Scholarship Docs
          </Button>
        </div>
      </div>

      {/* Recent tasks */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="w-4 h-4 text-indigo-500" />
            Recent Tasks
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-10 px-6">
              No tasks yet. Use Quick Actions above to start scraping.
            </p>
          ) : (
            <div className="divide-y">
              {(tasks as any[]).slice(0, 10).map((task) => {
                const result = parseTaskResult(task);
                const dur = taskDuration(task);
                return (
                  <div
                    key={task.id}
                    className="flex items-center justify-between px-5 py-3 hover:bg-muted/40 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {task.type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDistanceToNow(new Date(task.created_at + 'Z'), { addSuffix: true })}
                        {dur && ` · ${dur}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-4 text-right">
                      {result && (
                        <span className="text-xs text-muted-foreground tabular-nums">{result}</span>
                      )}
                      {task.error && (
                        <span className="text-xs text-red-500 max-w-[160px] truncate" title={task.error}>
                          {task.error}
                        </span>
                      )}
                      <StatusPill status={task.status} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
