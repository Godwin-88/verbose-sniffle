import { useState, useEffect, useMemo } from 'react';
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
import {
  Search, Database, MoreHorizontal, FileText,
  ChevronLeft, ChevronRight, Send,
  ChevronUp, ChevronDown, ChevronsUpDown,
} from 'lucide-react';
import { getStats } from '@/api/stats';

const STATUS_TABS = [
  { value: 'ready_for_review', label: 'Ready' },
  { value: 'pending',          label: 'Pending' },
  { value: 'approved',         label: 'Approved' },
  { value: 'dispatched',       label: 'Dispatched' },
  { value: 'rejected',         label: 'Rejected' },
];

const PER_PAGE = 50;

type SortKey = 'title' | 'company' | 'scraped_at' | 'source' | 'match_score';
type SortDir = 'asc' | 'desc';

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

function SortIcon({ col, sortKey, dir }: { col: SortKey; sortKey: SortKey; dir: SortDir }) {
  if (col !== sortKey) return <ChevronsUpDown className="inline w-3 h-3 ml-1 opacity-30" />;
  return dir === 'asc'
    ? <ChevronUp className="inline w-3 h-3 ml-1" />
    : <ChevronDown className="inline w-3 h-3 ml-1" />;
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
  const [sourceFilter, setSourceFilter] = useState('all');
  const [sortKey, setSortKey] = useState<SortKey>('scraped_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const debouncedSearch = useDebounce(search, 300);

  useEffect(() => {
    const s = searchParams.get('status');
    if (s && s !== status) setStatus(s);
  }, [searchParams]);

  const handleTabChange = (s: string) => {
    setStatus(s);
    setPage(1);
    setSearchParams({ status: s });
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'scraped_at' ? 'desc' : 'asc');
    }
    setPage(1);
  };

  const { data: jobsData, isLoading } = useQuery({
    queryKey: ['jobs', status, page],
    queryFn: () => getJobs({ status, page, per_page: PER_PAGE }),
    enabled: !debouncedSearch,
  });

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['jobs-search', debouncedSearch],
    queryFn: () => searchJobs(debouncedSearch),
    enabled: !!debouncedSearch,
  });

  const rawJobs: Job[] = debouncedSearch
    ? (searchResults || [])
    : (jobsData?.data || []);

  // Client-side filter + sort
  const jobs = useMemo(() => {
    let list = sourceFilter !== 'all'
      ? rawJobs.filter(j => j.source === sourceFilter)
      : rawJobs;

    list = [...list].sort((a, b) => {
      let av: string | number = '';
      let bv: string | number = '';
      if (sortKey === 'match_score') {
        av = a.match_score ?? -1;
        bv = b.match_score ?? -1;
      } else if (sortKey === 'scraped_at') {
        av = a.scraped_at ?? '';
        bv = b.scraped_at ?? '';
      } else {
        av = ((a as unknown as Record<string, unknown>)[sortKey] as string) ?? '';
        bv = ((b as unknown as Record<string, unknown>)[sortKey] as string) ?? '';
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return list;
  }, [rawJobs, sourceFilter, sortKey, sortDir]);

  // Unique sources for filter dropdown
  const sources = useMemo(() => {
    const s = new Set(rawJobs.map(j => j.source).filter(Boolean));
    return Array.from(s).sort();
  }, [rawJobs]);

  const total: number = debouncedSearch ? jobs.length : (jobsData?.total || 0);
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  });

  const getBadge = (s: string) => stats?.jobs?.[s] || 0;

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
    const srcs = JSON.parse(localStorage.getItem('jh_settings_sources') || '[]');
    run(
      () => scrapeJobs({ keywords: keywords.length ? keywords : undefined, sources: srcs.length ? srcs : undefined }),
      'Scrape Jobs',
      [['jobs']]
    );
  };

  const handleGenerateDocs = () => {
    run(() => generateJobDocs({}), 'Generate AI Docs', [['jobs']]);
  };

  const thClass = 'cursor-pointer select-none hover:text-foreground transition-colors';

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
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9"
          />
        </div>
        <Select value={sourceFilter} onValueChange={(v) => { setSourceFilter(v); setPage(1); }}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sources</SelectItem>
            {sources.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {(sourceFilter !== 'all' || debouncedSearch) && (
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
              <TableHead className={thClass} onClick={() => handleSort('title')}>
                Title <SortIcon col="title" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className={thClass} onClick={() => handleSort('company')}>
                Company <SortIcon col="company" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className={thClass} onClick={() => handleSort('scraped_at')}>
                Date Posted <SortIcon col="scraped_at" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className={thClass} onClick={() => handleSort('source')}>
                Source <SortIcon col="source" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className={`w-[120px] ${thClass}`} onClick={() => handleSort('match_score')}>
                Match <SortIcon col="match_score" sortKey={sortKey} dir={sortDir} />
              </TableHead>
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
                  <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                    {job.scraped_at
                      ? new Date(job.scraped_at).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })
                      : job.deadline || '—'}
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
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <JobDetailPanel jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />

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
