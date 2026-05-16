import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getJobReplies, markReplyRead, type EmailReply } from '@/api/jobs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { Mail, Copy, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useState } from 'react';

const CATEGORY_CONFIG: Record<EmailReply['category'], { label: string; className: string }> = {
  interview_invite: { label: '🎉 Interview Invite', className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  offer:            { label: '🏆 Job Offer',        className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  info_request:     { label: '❓ Info Request',     className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  rejection:        { label: '✗ Rejection',          className: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' },
  acknowledgement:  { label: 'Acknowledgement',      className: 'bg-muted text-muted-foreground' },
  unknown:          { label: 'Reply',                className: 'bg-muted text-muted-foreground' },
};

export function RepliesTab({ jobId }: { jobId: string }) {
  const qc = useQueryClient();
  const [expandedDraft, setExpandedDraft] = useState<string | null>(null);

  const { data: replies = [], isLoading } = useQuery({
    queryKey: ['job-replies', jobId],
    queryFn: () => getJobReplies(jobId),
    refetchInterval: 30_000,
  });

  const readMutation = useMutation({
    mutationFn: markReplyRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-replies', jobId] });
      qc.invalidateQueries({ queryKey: ['stats'] });
    },
  });

  const copyDraft = (draft: string) => {
    navigator.clipboard.writeText(draft);
    toast.success('Draft copied to clipboard');
  };

  if (isLoading) {
    return <p className="text-sm text-muted-foreground py-8 text-center">Loading replies…</p>;
  }

  if (replies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center space-y-2">
        <Mail className="w-8 h-8 text-muted-foreground/40" />
        <p className="text-sm font-medium text-muted-foreground">No replies yet</p>
        <p className="text-xs text-muted-foreground max-w-xs">
          When employers reply to your application, their emails will appear here automatically via the n8n Gmail workflow.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {replies.map((reply) => {
        const config = CATEGORY_CONFIG[reply.category] ?? CATEGORY_CONFIG.unknown;
        const isUnread = !reply.is_read;
        const isDraftOpen = expandedDraft === reply.id;
        const timeAgo = (() => {
          try { return formatDistanceToNow(new Date(reply.received_at), { addSuffix: true }); }
          catch { return reply.received_at; }
        })();

        return (
          <div
            key={reply.id}
            className={`rounded-lg border p-4 space-y-3 transition-colors ${
              isUnread ? 'border-primary/30 bg-primary/5' : 'border-border bg-card'
            }`}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-0.5 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold truncate">
                    {reply.from_name || reply.from_email}
                  </span>
                  {isUnread && (
                    <span className="inline-block w-2 h-2 rounded-full bg-primary shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground truncate">{reply.from_email}</p>
                <p className="text-sm font-medium mt-1">{reply.subject}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge className={`text-xs ${config.className} border-0`}>
                  {config.label}
                </Badge>
                <span className="text-xs text-muted-foreground whitespace-nowrap">{timeAgo}</span>
              </div>
            </div>

            {/* Email body */}
            <p className="text-sm text-muted-foreground leading-relaxed line-clamp-4 whitespace-pre-wrap">
              {reply.body_text}
            </p>

            {/* AI draft reply */}
            {reply.ai_draft && (
              <div className="rounded-md border border-primary/20 bg-primary/5 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                    AI-drafted reply
                  </p>
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() => setExpandedDraft(isDraftOpen ? null : reply.id)}
                    >
                      {isDraftOpen ? 'Hide' : 'Show'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs gap-1"
                      onClick={() => copyDraft(reply.ai_draft!)}
                    >
                      <Copy className="w-3 h-3" /> Copy
                    </Button>
                  </div>
                </div>
                {isDraftOpen && (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
                    {reply.ai_draft}
                  </p>
                )}
              </div>
            )}

            {/* Mark read */}
            {isUnread && (
              <div className="flex justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs gap-1 text-muted-foreground"
                  onClick={() => readMutation.mutate(reply.id)}
                  disabled={readMutation.isPending}
                >
                  <CheckCircle className="w-3 h-3" /> Mark as read
                </Button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
