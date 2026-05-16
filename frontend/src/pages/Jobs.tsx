import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { getJobs, scrapeJobs, generateJobDocs, deleteJob, markJobDispatched, searchJobs } from '@/api/jobs';
import type { Job } from '@/api/jobs';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { StatusPill } from '@/components/shared/StatusPill';
import { MatchBar } from '@/components/shared/MatchBar';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { JobDetailPanel } from '@/components/jobs/JobDetailPanel';
import { useQuickAction } from '@/hooks/useQuickAction';
import { toast } from 'sonner';
import { Search, Database, MoreHorizontal, FileText, ChevronLeft, ChevronRight, Send } from 'lucide-react';
import { getStats } from '@/api/stats';

const STATUS_TABS = [
  { value: 'ready_for_review', label: 'Ready' },
  { value: 'pending',          label: 'Pending' },
  { value: 'approved',         label: 'Approved' },
  { value: 'dispatched',       label: 'Dispatched' },
  { value: 'rejected',         label: 'Rejected' },
];

const PER_PAGE = 50;

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const { run } = useQuickAction();

  const statusFromUrl = searchParams.get('status') || 'ready_for_review';
  const [status, setStatus] = useState(statusFromUrl);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const debouncedSearch = useDebounce(search, 300);

  // Sync URL → tab state
  useEffect(() => {
    const s = searchParams.get('status');
    if (s && s !== status) setStatus(s);
  }, [searchParams]);

  const handleTabChange = (s: string) => {
    setStatus(s);
    setPage(1);
    setSearchParams({ status: s });
  };

  // Main jobs query
  const { data: jobsData, isLoading } = useQuery({
    queryKey: ['jobs', status, page],
    queryFn: () => getJobs({ status, page, per_page: PER_PAGE }),
    enabled: !debouncedSearch,
  });

  // Search query
  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['jobs-search', debouncedSearch],
    queryFn: () => searchJobs(debouncedSearch),
    enabled: !!debouncedSearch,
  });

  const jobs: Job[] = debouncedSearch
    ? (searchResults || [])
    : (jobsData?.data || []);

  const total: number = debouncedSearch ? jobs.length : (jobsData?.total || 0);
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  // Stats for tab badges
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  });

  const getBadge = (s: string) => {
    if (!stats) return 0;
    return stats.jobs?.[s] || 0;
  };

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      qc.invalidateQueries({ queryKey: ['stats'] });
      toast.success('Job deleted');
      setConfirmDelete(null);
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: markJobDispatched,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      qc.invalidateQueries({ queryKey: ['stats'] });
      toast.success('Marked as dispatched');
    },
  });

  const handleScrape = () => {
    const keywords = (localStorage.getItem('jh_settings_keywords') || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    const sources = JSON.parse(localStorage.getItem('jh_settings_sources') || '[]');
    run(
      () => scrapeJobs({ keywords: keywords.length ? keywords : undefined, sources: sources.length ? sources : undefined }),
      'Scrape Jobs',
      [['jobs']]
    );
  };

  const handleGenerateDocs = () => {
    run(() => generateJobDocs({}), 'Generate AI Docs', [['jobs']]);
  };

  const isDeadlineSoon = (deadline: string) => {
    if (!deadline) return false;
    const d = new Date(deadline);
    return !isNaN(d.getTime()) && d < new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
  };

  return (
    <div className="space-y-5 pb-10">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleGenerateDocs}>
            <FileText className="w-4 h-4 mr-2" /> Generate AI Docs
          </Button>
          <Button size="sm" onClick={handleScrape}>
            <Database className="w-4 h-4 mr-2" /> Scrape Now
          </Button>
        </div>
      </div>

      {/* Status tabs */}
      <Tabs value={status} onValueChange={handleTabChange}>
        <TabsList className="bg-muted/50 p-1 h-auto flex-wrap">
          {STATUS_TABS.map((s) => {
            const count = getBadge(s.value);
            return (
              <TabsTrigger key={s.value} value={s.value} className="px-3 py-1.5 gap-2">
                {s.label}
                {count > 0 && (
                  <Badge
                    variant="secondary"
                    className={`text-[10px] px-1.5 h-4 ${s.value === 'ready_for_review' ? 'bg-amber-500 text-white' : ''}`}
                  >
                    {count}
                  </Badge>
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9"
          />
        </div>
        <Select defaultValue="all">
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Sector" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sectors</SelectItem>
            <SelectItem value="technology">Technology</SelectItem>
            <SelectItem value="ngo">NGO / INGO</SelectItem>
            <SelectItem value="government">Government</SelectItem>
            <SelectItem value="finance">Finance</SelectItem>
            <SelectItem value="health">Health</SelectItem>
          </SelectContent>
        </Select>
        {debouncedSearch && (
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {jobs.length} result{jobs.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="border rounded-lg bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Deadline</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="w-[120px]">Match</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading || searchLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            ) : jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                  {debouncedSearch
                    ? `No jobs matching "${debouncedSearch}"`
                    : 'No jobs in this status. Try scraping or changing the filter.'}
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((job) => (
                <TableRow
                  key={job.id}
                  className="cursor-pointer hover:bg-muted/30"
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <TableCell className="font-medium max-w-[220px] truncate" title={job.title}>
                    {job.title}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{job.company}</TableCell>
                  <TableCell
                    className={isDeadlineSoon(job.deadline) ? 'text-red-500 font-semibold' : 'text-muted-foreground'}
                  >
                    {job.deadline || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs font-normal">
                      {job.source}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <MatchBar score={job.match_score} />
                  </TableCell>
                  <TableCell>
                    <StatusPill status={job.status} />
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setSelectedJobId(job.id)}>
                          Review
                        </DropdownMenuItem>
                        {job.status === 'approved' && (
                          <DropdownMenuItem
                            onClick={() => dispatchMutation.mutate(job.id)}
                            disabled={dispatchMutation.isPending}
                          >
                            <Send className="w-3 h-3 mr-2" /> Mark Dispatched
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600"
                          onClick={() => setConfirmDelete(job.id)}
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {!debouncedSearch && total > PER_PAGE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{total} total · page {page} of {totalPages}</span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline" size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Detail panel */}
      <JobDetailPanel
        jobId={selectedJobId}
        onClose={() => setSelectedJobId(null)}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete job?"
        description="This will permanently remove the job and all generated documents. This cannot be undone."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => confirmDelete && deleteMutation.mutate(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}
