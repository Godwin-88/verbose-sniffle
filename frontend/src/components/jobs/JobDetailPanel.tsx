import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getJob, approveJob, rejectJob, deleteJob } from '@/api/jobs';
import type { Job } from '@/api/jobs';
import { RepliesTab } from './RepliesTab';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MatchBar } from '@/components/shared/MatchBar';
import { ResumeInsights } from '@/components/shared/ResumeInsights';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { ExportButton } from '@/components/shared/ExportButton';
import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import MDEditor from '@uiw/react-md-editor';
import { toast } from 'sonner';
import { Check, X, ArrowLeft, ExternalLink, Trash2 } from 'lucide-react';

interface Props {
  jobId: string | null;
  onClose: () => void;
}

const TAB_TRIGGER =
  'data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-0 text-sm';

export function JobDetailPanel({ jobId, onClose }: Props) {
  const qc = useQueryClient();

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId,
  });

  const [coverLetter, setCoverLetter] = useState('');
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (job) setCoverLetter(job.cover_letter || '');
  }, [job]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['jobs'] });
    qc.invalidateQueries({ queryKey: ['stats'] });
  };

  const approveMutation = useMutation({
    mutationFn: (data: Partial<Job>) => approveJob(jobId!, data),
    onSuccess: () => { invalidate(); toast.success('Approved & saved'); onClose(); },
    onError: () => toast.error('Failed to approve'),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectJob(jobId!),
    onSuccess: () => { invalidate(); toast.success('Rejected'); setConfirmReject(false); onClose(); },
    onError: () => toast.error('Failed to reject'),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteJob(jobId!),
    onSuccess: () => { invalidate(); toast.success('Deleted'); setConfirmDelete(false); onClose(); },
    onError: () => toast.error('Failed to delete'),
  });

  if (!jobId) return null;

  const tailoredResume = job?.tailored_resume;

  return (
    <>
      <Sheet open={!!jobId} onOpenChange={(open) => !open && onClose()}>
        <SheetContent className="sm:max-w-[640px] w-full h-full flex flex-col p-0 gap-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading…
            </div>
          ) : !job ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Job not found
            </div>
          ) : (
            <>
              {/* Header */}
              <SheetHeader className="p-5 border-b space-y-3 shrink-0">
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 shrink-0">
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">Back to list</span>
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto flex items-center gap-1 text-xs text-primary hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View posting <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <SheetTitle className="text-lg font-bold leading-tight">
                  {job.title}
                  <span className="font-normal text-muted-foreground"> @ {job.company}</span>
                </SheetTitle>
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{job.source}</span>
                  {job.location && <><span>·</span><span>{job.location}</span></>}
                  {job.deadline && <><span>·</span><span>Deadline: {job.deadline}</span></>}
                </div>
                <div className="flex items-center gap-4 pt-1">
                  <MatchBar score={job.match_score} />
                  <Badge variant="outline" className="ml-auto capitalize text-[10px] tracking-wider">
                    {job.status.replace(/_/g, ' ')}
                  </Badge>
                </div>
              </SheetHeader>

              {/* Tabs */}
              <Tabs defaultValue="cover-letter" className="flex-1 flex flex-col min-h-0">
                <div className="px-5 border-b shrink-0">
                  <TabsList className="w-full justify-start h-11 bg-transparent gap-5 rounded-none p-0">
                    <TabsTrigger value="cover-letter" className={TAB_TRIGGER}>
                      Cover Letter
                    </TabsTrigger>
                    <TabsTrigger value="resume" className={TAB_TRIGGER}>
                      Resume Insights
                    </TabsTrigger>
                    <TabsTrigger value="full" className={TAB_TRIGGER}>
                      Full Package
                    </TabsTrigger>
                    <TabsTrigger value="replies" className={TAB_TRIGGER}>
                      Replies
                    </TabsTrigger>
                  </TabsList>
                </div>

                <div className="flex-1 overflow-auto">
                  <TabsContent value="cover-letter" className="p-5 m-0 h-full" data-color-mode="light">
                    <MDEditor
                      value={coverLetter}
                      onChange={(v) => setCoverLetter(v || '')}
                      preview="edit"
                      height={480}
                    />
                  </TabsContent>

                  <TabsContent value="resume" className="p-5 m-0">
                    <ResumeInsights data={tailoredResume} />
                  </TabsContent>

                  <TabsContent value="full" className="p-5 m-0">
                    <div className="prose prose-sm max-w-none border rounded-lg p-5 bg-muted/10">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {job.full_doc_md || '_No full package generated yet._'}
                      </ReactMarkdown>
                    </div>
                  </TabsContent>

                  <TabsContent value="replies" className="p-5 m-0">
                    <RepliesTab jobId={job.id} />
                  </TabsContent>
                </div>
              </Tabs>

              {/* Footer actions */}
              <div className="p-4 border-t bg-muted/20 flex items-center gap-2 shrink-0">
                <Button
                  className="flex-1"
                  onClick={() => approveMutation.mutate({ cover_letter: coverLetter, full_doc_md: job.full_doc_md, tailored_resume: job.tailored_resume })}
                  disabled={approveMutation.isPending}
                >
                  <Check className="w-4 h-4 mr-2" />
                  {approveMutation.isPending ? 'Saving…' : 'Approve & Save'}
                </Button>
                <Button
                  variant="outline"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                  onClick={() => setConfirmReject(true)}
                  disabled={rejectMutation.isPending}
                >
                  <X className="w-4 h-4 mr-1" /> Reject
                </Button>
                <ExportButton type="jobs" id={jobId} filename={`${job.company}_${job.title}.pdf`} />
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-red-600"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmReject}
        title="Reject this job?"
        description="The job will be moved to Rejected and will not appear in the review queue."
        confirmLabel="Reject"
        destructive
        loading={rejectMutation.isPending}
        onConfirm={() => rejectMutation.mutate()}
        onCancel={() => setConfirmReject(false)}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this job?"
        description="This permanently removes the job and all generated documents. This cannot be undone."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
