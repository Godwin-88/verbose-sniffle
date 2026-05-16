import { useState, useRef, useEffect } from 'react';
import { Search, User, LogOut } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { supabase } from '@/lib/supabase';
import { useQuery } from '@tanstack/react-query';
import { searchJobs } from '@/api/jobs';
import { searchScholarships } from '@/api/scholarships';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

function useDebounce<T>(value: T, delay: number): T {
  const [d, setD] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setD(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return d;
}

export function Topbar() {
  const { userId, logout } = useAuthStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dq = useDebounce(query, 300);

  const { data: jobResults = [] } = useQuery({
    queryKey: ['search-jobs', dq],
    queryFn: () => searchJobs(dq),
    enabled: dq.length > 1,
  });

  const { data: scholResults = [] } = useQuery({
    queryKey: ['search-schols', dq],
    queryFn: () => searchScholarships(dq),
    enabled: dq.length > 1,
  });

  const hasResults = dq.length > 1 && (jobResults.length > 0 || scholResults.length > 0);
  const showDropdown = open && dq.length > 1;

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelect = (type: 'jobs' | 'scholarships', id: string) => {
    navigate(`/${type}?selected=${id}`);
    setQuery('');
    setOpen(false);
  };

  return (
    <header className="h-14 border-b bg-background flex items-center justify-between px-4 md:px-6 shrink-0">
      {/* Search */}
      <div className="flex-1 max-w-md relative" ref={wrapperRef}>
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          type="search"
          placeholder="Search jobs & scholarships…"
          className="pl-9 bg-muted/50 focus-visible:bg-background"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
        />
        {showDropdown && (
          <div className="absolute top-full mt-1 w-full bg-popover border rounded-lg shadow-lg z-50 overflow-hidden max-h-80 overflow-y-auto">
            {!hasResults ? (
              <div className="px-4 py-3 text-sm text-muted-foreground">
                No results for "{dq}"
              </div>
            ) : (
              <>
                {jobResults.slice(0, 5).map((j: any) => (
                  <button
                    key={j.id}
                    className="w-full text-left px-4 py-2.5 hover:bg-muted transition-colors flex items-start gap-3"
                    onClick={() => handleSelect('jobs', j.id)}
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500 mt-0.5 w-14 shrink-0">
                      JOB
                    </span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{j.title}</div>
                      <div className="text-xs text-muted-foreground truncate">{j.company}</div>
                    </div>
                  </button>
                ))}
                {scholResults.slice(0, 5).map((s: any) => (
                  <button
                    key={s.id}
                    className="w-full text-left px-4 py-2.5 hover:bg-muted transition-colors flex items-start gap-3"
                    onClick={() => handleSelect('scholarships', s.id)}
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-green-600 mt-0.5 w-14 shrink-0">
                      SCHOL
                    </span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{s.title}</div>
                      <div className="text-xs text-muted-foreground truncate">{s.funder || s.company}</div>
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2 ml-4">
            <User className="w-4 h-4" />
            <span className="hidden md:inline text-sm max-w-[120px] truncate">
              {userId || 'User'}
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem onClick={() => navigate('/profile')}>
            Profile
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate('/settings')}>
            Settings
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-red-600 focus:text-red-600"
            onClick={async () => { await supabase.auth.signOut(); logout(); navigate('/setup'); }}
          >
            <LogOut className="w-4 h-4 mr-2" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
