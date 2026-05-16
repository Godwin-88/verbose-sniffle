import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getScholarship, approveScholarship, rejectScholarship, deleteScholarship } from '@/api/scholarships';
import type { Scholarship } from '@/api/scholarships';
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
  scholId: string | null;
  onClose: () => void;
}

const TAB_TRIGGER =
  'data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-0 text-sm whitespace-nowrap';

export function ScholarshipDetailPanel({ scholId, onClose }: Props) {
  const qc = useQueryClient();

  const { data: schol, isLoading } = useQuery({
    queryKey: ['scholarship', scholId],
    queryFn: () => getScholarship(scholId!),
    enabled: !!scholId,
  });

  const [motivationLetter, setMotivationLetter] = useState('');
  const [researchProposal, setResearchProposal] = useState('');
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (schol) {
      setMotivationLetter(schol.motivation_letter || '');
      setResearchProposal(schol.research_proposal || '');
    }
  }, [schol]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['scholarships'] });
    qc.invalidateQueries({ queryKey: ['stats'] });
  };

  const approveMutation = useMutation({
    mutationFn: (data: Partial<Scholarship>) => approveScholarship(scholId!, data),
    onSuccess: () => { invalidate(); toast.success('Scholarship approved & saved'); onClose(); },
    onError: () => toast.error('Failed to approve'),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectScholarship(scholId!),
    onSuccess: () => { invalidate(); toast.success('Rejected'); setConfirmReject(false); onClose(); },
    onError: () => toast.error('Failed to reject'),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteScholarship(scholId!),
    onSuccess: () => { invalidate(); toast.success('Deleted'); setConfirmDelete(false); onClose(); },
    onError: () => toast.error('Failed to delete'),
  });

  if (!scholId) return null;

  const isPhd = schol?.level?.toLowerCase().includes('phd');
  const funder = schol?.funder || schol?.company;
  const fundingType = schol?.funding_type;

  const fundingBadgeClass =
    fundingType === 'fully_funded'
      ? 'bg-green-100 text-green-700 border-green-200'
      : fundingType === 'partially_funded'
      ? 'bg-amber-100 text-amber-700 border-amber-200'
      : '';

  return (
    <>
      <Sheet open={!!scholId} onOpenChange={(open) => !open && onClose()}>
        <SheetContent className="sm:max-w-[640px] w-full h-full flex flex-col p-0 gap-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">Loading…</div>
          ) : !schol ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">Not found</div>
          ) : (
            <>
              {/* Header */}
              <SheetHeader className="p-5 border-b space-y-3 shrink-0">
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 shrink-0">
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">Back to list</span>
                  {schol.url && (
                    <a
                      href={schol.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto flex items-center gap-1 text-xs text-primary hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Official page <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <SheetTitle className="text-lg font-bold leading-tight">
                  {schol.title}
                </SheetTitle>
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  {funder && <span>{funder}</span>}
                  {schol.funder_country && <><span>·</span><span>{schol.funder_country}</span></>}
                  {schol.level && <><span>·</span><span className="capitalize">{schol.level}</span></>}
                  {schol.deadline && <><span>·</span><span>Deadline: {schol.deadline}</span></>}
                </div>
                <div className="flex items-center gap-3 pt-1 flex-wrap">
                  <MatchBar score={schol.match_score} />
                  {fundingType && (
                    <Badge variant="outline" className={`text-[10px] capitalize ${fundingBadgeClass}`}>
                      {fundingType.replace(/_/g, ' ')}
                    </Badge>
                  )}
                  <Badge variant="outline" className="capitalize text-[10px] ml-auto tracking-wider">
                    {schol.status.replace(/_/g, ' ')}
                  </Badge>
                </div>
              </SheetHeader>

              {/* Tabs */}
              <Tabs defaultValue="motivation-letter" className="flex-1 flex flex-col min-h-0">
                <div className="px-5 border-b shrink-0 overflow-x-auto">
                  <TabsList className="w-max justify-start h-11 bg-transparent gap-5 rounded-none p-0">
                    <TabsTrigger value="motivation-letter" className={TAB_TRIGGER}>
                      Motivation Letter
                    </TabsTrigger>
                    <TabsTrigger value="cv-tailoring" className={TAB_TRIGGER}>
                      CV Tailoring
                    </TabsTrigger>
                    {isPhd && (
                      <TabsTrigger value="research-proposal" className={TAB_TRIGGER}>
                        Research Proposal
                      </TabsTrigger>
                    )}
                    <TabsTrigger value="full" className={TAB_TRIGGER}>
                      Full Package
                    </TabsTrigger>
                  </TabsList>
                </div>

                <div className="flex-1 overflow-auto">
                  <TabsContent value="motivation-letter" className="p-5 m-0" data-color-mode="light">
                    <MDEditor
                      value={motivationLetter}
                      onChange={(v) => setMotivationLetter(v || '')}
                      preview="edit"
                      height={480}
                    />
                  </TabsContent>

                  <TabsContent value="cv-tailoring" className="p-5 m-0">
                    <ResumeInsights data={schol.tailored_resume} showStrengthsGaps />
                  </TabsContent>

                  {isPhd && (
                    <TabsContent value="research-proposal" className="p-5 m-0" data-color-mode="light">
                      <MDEditor
                        value={researchProposal}
                        onChange={(v) => setResearchProposal(v || '')}
                        preview="edit"
                        height={480}
                      />
                    </TabsContent>
                  )}

                  <TabsContent value="full" className="p-5 m-0">
                    <div className="prose prose-sm max-w-none border rounded-lg p-5 bg-muted/10">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {schol.full_doc_md || '_No full package generated yet._'}
                      </ReactMarkdown>
                    </div>
                  </TabsContent>
                </div>
              </Tabs>

              {/* Footer actions */}
              <div className="p-4 border-t bg-muted/20 flex items-center gap-2 shrink-0">
                <Button
                  className="flex-1"
                  onClick={() => approveMutation.mutate({
                    motivation_letter: motivationLetter,
                    research_proposal: researchProposal,
                    tailored_resume: schol.tailored_resume,
                    full_doc_md: schol.full_doc_md,
                  })}
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
                <ExportButton type="scholarships" id={scholId} filename={`${schol.title}.pdf`} />
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
        title="Reject this scholarship?"
        description="It will be moved to Rejected and removed from the review queue."
        confirmLabel="Reject"
        destructive
        loading={rejectMutation.isPending}
        onConfirm={() => rejectMutation.mutate()}
        onCancel={() => setConfirmReject(false)}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this scholarship?"
        description="This permanently removes the scholarship and all generated documents."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
