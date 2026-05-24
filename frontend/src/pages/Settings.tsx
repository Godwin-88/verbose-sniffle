import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { getHealth, sendReminderDigest, getUpcomingReminders } from '@/api/stats';
import { toast } from 'sonner';
import { Bell, Database, Send, CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

const JOB_SOURCES = [
  // Kenya
  'BrighterMonday', 'Fuzu', 'LinkedIn', 'GAA', 'NEAIMS',
  'MyJobMag', 'JobWebKenya', 'CareersInKenya', 'NGOJobsKenya', 'Reddit',
  // Remote / Global
  'RemoteOK', 'WeWorkRemotely', 'RemoteForAfrica', 'Himalayas',
];

function usePersisted<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : initial;
    } catch { return initial; }
  });
  const set = (v: T) => { setValue(v); localStorage.setItem(key, JSON.stringify(v)); };
  return [value, set];
}

export default function Settings() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: getHealth });

  // Scraping defaults
  const [keywords, setKeywords]         = usePersisted('jh_settings_keywords', '');
  const [sources, setSources]           = usePersisted<string[]>('jh_settings_sources', []);

  // Reminder preferences
  const [remindersOn, setRemindersOn]   = usePersisted('jh_reminders_enabled', true);
  const [deadlineDays, setDeadlineDays] = usePersisted('jh_reminder_deadline_days', '7');
  const [staleHours, setStaleHours]     = usePersisted('jh_reminder_stale_hours', '48');

  const toggleSource = (s: string) =>
    setSources(sources.includes(s) ? sources.filter(x => x !== s) : [...sources, s]);

  // Reminder preview — how many items would be in today's digest
  const { data: remindersPreview, isLoading: previewLoading } = useQuery({
    queryKey: ['reminders-preview', deadlineDays, staleHours],
    queryFn: () => getUpcomingReminders({
      deadline_days: Number(deadlineDays),
      stale_hours: Number(staleHours),
    }),
    enabled: remindersOn,
    staleTime: 60_000,
  });

  const digestMutation = useMutation({
    mutationFn: () => sendReminderDigest({
      deadline_days: Number(deadlineDays),
      stale_hours: Number(staleHours),
    }),
    onSuccess: (data) => {
      if (data.sent) toast.success('Digest email sent — check your inbox');
      else toast.error('Email not sent — check your SMTP/SendGrid config in the backend .env');
    },
    onError: () => toast.error('Failed to send digest'),
  });

  const summary = remindersPreview?.summary;
  const totalItems = summary
    ? summary.expiring_jobs + summary.expiring_scholarships + summary.stale_jobs + summary.stale_schols
    : 0;

  return (
    <div className="max-w-3xl space-y-8 pb-10">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* ── Scraping ── */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-base font-semibold">Scraping Defaults</h2>
        </div>
        <Card>
          <CardContent className="p-6 space-y-6">
            <div className="space-y-2">
              <Label>Keywords <span className="text-muted-foreground font-normal">(comma-separated)</span></Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="data analyst, software engineer, project manager"
              />
              <p className="text-xs text-muted-foreground">
                Used automatically when you trigger a Scrape from the dashboard.
              </p>
            </div>

            <div className="space-y-3">
              <Label>Job Sources</Label>
              <div className="grid grid-cols-2 gap-2.5">
                {JOB_SOURCES.map(src => (
                  <label key={src} className="flex items-center gap-2.5 cursor-pointer group">
                    <Checkbox
                      checked={sources.includes(src)}
                      onCheckedChange={() => toggleSource(src)}
                    />
                    <span className="text-sm group-hover:text-foreground transition-colors">
                      {src}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ── Reminders ── */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-base font-semibold">Deadline Reminders</h2>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-medium">Daily digest email</CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  n8n sends a grouped reminder email each weekday at 8am covering expiring deadlines and stale approvals.
                </CardDescription>
              </div>
              <Switch
                checked={remindersOn}
                onCheckedChange={setRemindersOn}
              />
            </div>
          </CardHeader>

          {remindersOn && (
            <CardContent className="space-y-6 pt-0">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs">Warn me when deadline is within</Label>
                  <Select value={deadlineDays} onValueChange={setDeadlineDays}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="3">3 days</SelectItem>
                      <SelectItem value="5">5 days</SelectItem>
                      <SelectItem value="7">7 days</SelectItem>
                      <SelectItem value="14">14 days</SelectItem>
                      <SelectItem value="30">30 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs">Alert for approved-but-unsubmitted after</Label>
                  <Select value={staleHours} onValueChange={setStaleHours}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="24">24 hours</SelectItem>
                      <SelectItem value="48">48 hours</SelectItem>
                      <SelectItem value="72">72 hours</SelectItem>
                      <SelectItem value="168">1 week</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Preview of what today's digest would contain */}
              <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Today's digest preview
                  </p>
                  {previewLoading && (
                    <span className="text-xs text-muted-foreground animate-pulse">Loading…</span>
                  )}
                </div>

                {summary && (
                  <div className="grid grid-cols-2 gap-2">
                    <PreviewStat
                      icon={<Clock className="w-3.5 h-3.5" />}
                      label={`Jobs expiring in ${deadlineDays}d`}
                      value={summary.expiring_jobs}
                      warn={summary.expiring_jobs > 0}
                    />
                    <PreviewStat
                      icon={<Clock className="w-3.5 h-3.5" />}
                      label={`Scholarships expiring in ${deadlineDays}d`}
                      value={summary.expiring_scholarships}
                      warn={summary.expiring_scholarships > 0}
                    />
                    <PreviewStat
                      icon={<AlertTriangle className="w-3.5 h-3.5" />}
                      label="Stale approved jobs"
                      value={summary.stale_jobs}
                      warn={summary.stale_jobs > 0}
                    />
                    <PreviewStat
                      icon={<AlertTriangle className="w-3.5 h-3.5" />}
                      label="Stale approved scholarships"
                      value={summary.stale_schols}
                      warn={summary.stale_schols > 0}
                    />
                  </div>
                )}

                {summary && totalItems === 0 && (
                  <div className="flex items-center gap-2 text-xs text-green-600 dark:text-green-400">
                    <CheckCircle2 className="w-4 h-4" />
                    Nothing urgent — digest would be skipped today.
                  </div>
                )}
              </div>

              {/* Manual send */}
              <div className="flex items-center justify-between pt-1">
                <div>
                  <p className="text-sm font-medium">Send digest now</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Trigger a test digest immediately to your registered email.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => digestMutation.mutate()}
                  disabled={digestMutation.isPending}
                  className="gap-2"
                >
                  <Send className="w-3.5 h-3.5" />
                  {digestMutation.isPending ? 'Sending…' : 'Send now'}
                </Button>
              </div>

              {/* n8n setup hint */}
              <div className="rounded-md bg-primary/5 border border-primary/20 p-3 space-y-1">
                <p className="text-xs font-medium text-primary">n8n setup required for automated daily emails</p>
                <p className="text-xs text-muted-foreground">
                  Import <code className="font-mono bg-muted px-1 rounded">n8n_reminder_workflow.json</code> into n8n, set your API key credential, and activate the workflow. It runs every weekday at 8am automatically.
                </p>
              </div>
            </CardContent>
          )}
        </Card>
      </section>

      {/* ── System ── */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold">System</h2>
        <Card>
          <CardContent className="divide-y p-0">
            <Row
              label="API connection"
              description="Connection to your Job Hunter KE backend"
              value={
                <Badge
                  variant="secondary"
                  className={health?.db
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-red-100 text-red-700'}
                >
                  {health?.db ? 'Connected' : 'Disconnected'}
                </Badge>
              }
            />
            <Row
              label="Email provider"
              description="Configured in backend .env as EMAIL_PROVIDER"
              value={
                <span className="text-xs font-mono bg-muted px-2 py-1 rounded">
                  {health?.email_provider || 'smtp'}
                </span>
              }
            />
            <Row
              label="AI model"
              description="Model used for cover letters and CV tailoring"
              value={
                <span className="text-xs font-mono bg-muted px-2 py-1 rounded">
                  {health?.ai_model || 'configured in .env'}
                </span>
              }
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function PreviewStat({
  icon, label, value, warn,
}: { icon: React.ReactNode; label: string; value: number; warn: boolean }) {
  return (
    <div className={`flex items-center gap-2 rounded-md px-3 py-2 text-xs ${
      warn && value > 0
        ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400'
        : 'bg-background text-muted-foreground'
    }`}>
      {icon}
      <span className="flex-1">{label}</span>
      <span className="font-bold text-sm">{value}</span>
    </div>
  );
}

function Row({ label, description, value }: { label: string; description: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {value}
    </div>
  );
}
