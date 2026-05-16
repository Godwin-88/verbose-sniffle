import { Button } from '@/components/ui/button';
import { Download, Loader2 } from 'lucide-react';
import { useExport } from '@/hooks/useExport';

interface Props {
  type: 'jobs' | 'scholarships';
  id: string;
  filename?: string;
  variant?: "link" | "default" | "destructive" | "outline" | "secondary" | "ghost" | null | undefined;
}

export function ExportButton({ type, id, filename, variant = "outline" }: Props) {
  const { exportDocument, isExporting } = useExport();

  return (
    <Button 
      variant={variant}
      size="sm"
      onClick={() => exportDocument(type, id, filename)}
      disabled={isExporting}
    >
      {isExporting ? (
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        <Download className="w-4 h-4 mr-2" />
      )}
      Export PDF
    </Button>
  );
}
