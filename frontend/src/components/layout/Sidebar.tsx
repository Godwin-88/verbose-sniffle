import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  GraduationCap,
  Zap,
  User,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useQuery } from '@tanstack/react-query';
import { getStats } from '@/api/stats';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Briefcase, label: 'Jobs', path: '/jobs', badgeKey: 'jobs.ready_for_review', replyKey: 'unread_replies' },
  { icon: GraduationCap, label: 'Scholarships', path: '/scholarships', badgeKey: 'scholarships.ready_for_review' },
  { icon: Zap, label: 'Tasks', path: '/tasks' },
  { icon: User, label: 'Profile', path: '/profile' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export function Sidebar() {
  const location = useLocation();
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  });

  const getBadgeCount = (key: string) => {
    if (!stats) return 0;
    const parts = key.split('.');
    let current = stats;
    for (const part of parts) {
      current = current?.[part];
    }
    return typeof current === 'number' ? current : 0;
  };

  return (
    <aside className="hidden md:flex w-[220px] border-r h-screen bg-sidebar flex-col shrink-0">
      <div className="p-6 font-bold text-xl tracking-tight text-sidebar-foreground">
        Job Hunter KE
      </div>
      <nav className="flex-1 px-4 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const badgeCount = item.badgeKey ? getBadgeCount(item.badgeKey) : 0;
          const replyCount = (item as any).replyKey ? getBadgeCount((item as any).replyKey) : 0;

          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
              )}
            >
              <item.icon className="w-4 h-4" />
              <span className="flex-1">{item.label}</span>
              {replyCount > 0 && (
                <Badge variant="secondary" className="bg-blue-500 text-white hover:bg-blue-600" title="Unread employer replies">
                  {replyCount}
                </Badge>
              )}
              {badgeCount > 0 && (
                <Badge variant="secondary" className="bg-amber-500 text-white hover:bg-amber-600">
                  {badgeCount}
                </Badge>
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
