import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  getScholarships, scrapeScholarships, generateScholarshipDocs,
  deleteScholarship, markScholarshipDispatched, searchScholarships,
} from '@/api/scholarships';
import type { Scholarship } from '@/api/scholarships';
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
import { ScholarshipDetailPanel } from '@/components/scholarships/ScholarshipDetailPanel';
import { useQuickAction } from '@/hooks/useQuickAction';
import { toast } from 'sonner';
import {
  Search, Database, MoreHorizontal, FileText, ChevronLeft, ChevronRight, Globe, Send,
  ChevronUp, ChevronDown, ChevronsUpDown,
} from 'lucide-react';
import { getStats } from '@/api/stats';

type SortKey = 'title' | 'funder' | 'deadline' | 'level' | 'match_score';
type SortDir = 'asc' | 'desc';

function SortIcon({ col, sortKey, dir }: { col: SortKey; sortKey: SortKey; dir: SortDir }) {
  if (col !== sortKey) return <ChevronsUpDown className="inline w-3 h-3 ml-1 opacity-30" />;
  return dir === 'asc'
    ? <ChevronUp className="inline w-3 h-3 ml-1" />
    : <ChevronDown className="inline w-3 h-3 ml-1" />;
}

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

const FUNDING_LABEL: Record<string, string> = {
  fully_funded: 'Fully Funded',
  partially_funded: 'Partial',
  unknown: 'Unknown',
};

export default function Scholarships() {
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const { run } = useQuickAction();

  const statusFromUrl = searchParams.get('status') || 'ready_for_review';
  const [status, setStatus] = useState(statusFromUrl);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [fundingType, setFundingType] = useState('all');
  const [region, setRegion] = useState('all');
  const [level, setLevel] = useState('all');
  const [selectedScholId, setSelectedScholId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('deadline');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

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
      setSortDir(key === 'deadline' ? 'asc' : 'asc');
    }
    setPage(1);
  };

  const { data: scholsData, isLoading } = useQuery({
    queryKey: ['scholarships', status, page, fundingType, region, level],
    queryFn: () => getScholarships({
      status,
      page,
      per_page: PER_PAGE,
      funding_type: fundingType !== 'all' ? fundingType : undefined,
      region:       region !== 'all'       ? region       : undefined,
      level:        level !== 'all'        ? level        : undefined,
    }),
    enabled: !debouncedSearch,
  });

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['scholarships-search', debouncedSearch],
    queryFn: () => searchScholarships(debouncedSearch),
    enabled: !!debouncedSearch,
  });

  const rawScholarships: Scholarship[] = debouncedSearch
    ? (searchResults || [])
    : (scholsData?.data || []);

  const scholarships = useMemo(() => {
    return [...rawScholarships].sort((a, b) => {
      let av: string | number = '';
      let bv: string | number = '';
      if (sortKey === 'match_score') {
        av = a.match_score ?? -1;
        bv = b.match_score ?? -1;
      } else if (sortKey === 'deadline') {
        av = a.deadline ?? '';
        bv = b.deadline ?? '';
      } else if (sortKey === 'funder') {
        av = (a.funder || a.company || '').toLowerCase();
        bv = (b.funder || b.company || '').toLowerCase();
      } else {
        av = ((a as unknown as Record<string, unknown>)[sortKey] as string ?? '').toLowerCase();
        bv = ((b as unknown as Record<string, unknown>)[sortKey] as string ?? '').toLowerCase();
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [rawScholarships, sortKey, sortDir]);

  const total: number = debouncedSearch ? scholarships.length : (scholsData?.total || 0);
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  });

  const getBadge = (s: string) => stats?.scholarships?.[s] || 0;

  const deleteMutation = useMutation({
    mutationFn: deleteScholarship,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scholarships'] });
      qc.invalidateQueries({ queryKey: ['stats'] });
      toast.success('Scholarship deleted');
      setConfirmDelete(null);
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: markScholarshipDispatched,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scholarships'] });
      qc.invalidateQueries({ queryKey: ['stats'] });
      toast.success('Marked as dispatched');
    },
  });

  const handleScrape = () => {
    const keywords = (localStorage.getItem('jh_settings_keywords') || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    run(
      () => scrapeScholarships({ keywords: keywords.length ? keywords : undefined }),
      'Scrape Scholarships',
      [['scholarships']]
    );
  };

  const handleGenerateDocs = () => {
    run(() => generateScholarshipDocs({}), 'Generate Scholarship Docs', [['scholarships']]);
  };

  const isDeadlineSoon = (deadline: string) => {
    if (!deadline) return false;
    const d = new Date(deadline);
    return !isNaN(d.getTime()) && d < new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  };

  const fundingClass = (ft: string) => {
    if (ft === 'fully_funded') return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
    if (ft === 'partially_funded') return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
    return 'bg-muted text-muted-foreground';
  };

  return (
    <div className="space-y-5 pb-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scholarships</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleGenerateDocs}>
            <FileText className="w-4 h-4 mr-2" /> Generate AI Docs
          </Button>
          <Button size="sm" onClick={handleScrape}>
            <Database className="w-4 h-4 mr-2" /> Scrape Now
          </Button>
        </div>
      </div>

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

      {/* Toolbar with filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search scholarships…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9"
          />
        </div>
        <Select value={fundingType} onValueChange={(v) => { setFundingType(v); setPage(1); }}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Funding" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All funding</SelectItem>
            <SelectItem value="fully_funded">Fully Funded</SelectItem>
            <SelectItem value="partially_funded">Partial</SelectItem>
          </SelectContent>
        </Select>
        <Select value={region} onValueChange={(v) => { setRegion(v); setPage(1); }}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Region" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All regions</SelectItem>
            <SelectItem value="africa">Africa</SelectItem>
            <SelectItem value="europe">Europe</SelectItem>
            <SelectItem value="asia">Asia</SelectItem>
            <SelectItem value="americas">Americas</SelectItem>
            <SelectItem value="global">Global</SelectItem>
          </SelectContent>
        </Select>
        <Select value={level} onValueChange={(v) => { setLevel(v); setPage(1); }}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Level" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All levels</SelectItem>
            <SelectItem value="masters">Masters</SelectItem>
            <SelectItem value="phd">PhD</SelectItem>
            <SelectItem value="undergraduate">Undergraduate</SelectItem>
            <SelectItem value="short_course">Short Course</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="border rounded-lg bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('title')}>
                Title <SortIcon col="title" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('funder')}>
                Funder <SortIcon col="funder" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead>Country</TableHead>
              <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('level')}>
                Level <SortIcon col="level" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead>Funding</TableHead>
              <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('deadline')}>
                Deadline <SortIcon col="deadline" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead className="w-[120px] cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort('match_score')}>
                Match <SortIcon col="match_score" sortKey={sortKey} dir={sortDir} />
              </TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading || searchLoading ? (
              <TableRow>
                <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            ) : scholarships.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="h-32 text-center text-muted-foreground">
                  {debouncedSearch
                    ? `No scholarships matching "${debouncedSearch}"`
                    : 'No scholarships in this status. Try scraping.'}
                </TableCell>
              </TableRow>
            ) : (
              scholarships.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer hover:bg-muted/30"
                  onClick={() => setSelectedScholId(s.id)}
                >
                  <TableCell className="font-medium max-w-[200px] truncate" title={s.title}>
                    {s.title}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {s.funder || s.company}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-sm">
                      <Globe className="w-3 h-3 text-muted-foreground shrink-0" />
                      <span>{s.funder_country || s.country || '—'}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {s.level ? (
                      <Badge variant="outline" className="text-xs capitalize">
                        {s.level}
                      </Badge>
                    ) : '—'}
                  </TableCell>
                  <TableCell>
                    {s.funding_type ? (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${fundingClass(s.funding_type)}`}>
                        {FUNDING_LABEL[s.funding_type] || s.funding_type}
                      </span>
                    ) : '—'}
                  </TableCell>
                  <TableCell
                    className={isDeadlineSoon(s.deadline) ? 'text-red-500 font-semibold' : 'text-muted-foreground'}
                  >
                    {s.deadline || '—'}
                  </TableCell>
                  <TableCell>
                    <MatchBar score={s.match_score} />
                  </TableCell>
                  <TableCell>
                    <StatusPill status={s.status} />
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setSelectedScholId(s.id)}>
                          Review
                        </DropdownMenuItem>
                        {s.status === 'approved' && (
                          <DropdownMenuItem
                            onClick={() => dispatchMutation.mutate(s.id)}
                            disabled={dispatchMutation.isPending}
                          >
                            <Send className="w-3 h-3 mr-2" /> Mark Dispatched
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600"
                          onClick={() => setConfirmDelete(s.id)}
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

      <ScholarshipDetailPanel
        scholId={selectedScholId}
        onClose={() => setSelectedScholId(null)}
      />

      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete scholarship?"
        description="This will permanently remove the scholarship and all generated documents."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => confirmDelete && deleteMutation.mutate(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}
