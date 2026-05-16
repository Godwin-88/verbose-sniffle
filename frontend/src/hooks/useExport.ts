import { useState } from 'react';
import { apiClient } from '@/api/client';
import { toast } from 'sonner';

export function useExport() {
  const [isExporting, setIsExporting] = useState(false);

  const exportDocument = async (type: 'jobs' | 'scholarships', id: string, filename?: string) => {
    setIsExporting(true);
    try {
      const response = await apiClient.get(`/${type}/${id}/export`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename || `application_${id.slice(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success('Document exported successfully');
    } catch (error) {
      console.error('Export failed', error);
      toast.error('Failed to export document');
    } finally {
      setIsExporting(false);
    }
  };

  return { exportDocument, isExporting };
}
