import { apiClient } from './client';

export type JobStatus = 'pending' | 'ready_for_review' | 'approved' | 'dispatched' | 'rejected';

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  deadline: string;
  url: string;
  source: string;
  sector?: string;
  match_score?: number;
  status: 'pending' | 'ready_for_review' | 'approved' | 'dispatched' | 'rejected';
  cover_letter?: string;
  tailored_resume?: string;
  full_doc_md?: string;
  scraped_at: string;
}

export const getJobs = async (params: {
  status?: string;
  page?: number;
  per_page?: number;
  sector?: string;
}) => {
  const { data } = await apiClient.get('/jobs', { params });
  return data;
};

export const getJob = async (id: string) => {
  const { data } = await apiClient.get(`/jobs/${id}`);
  return data;
};

export const scrapeJobs = async (payload: { keywords?: string[]; sources?: string[] }) => {
  const { data } = await apiClient.post('/scrape', payload);
  return data;
};

export const generateJobDocs = async (payload: { job_id?: string; max?: number; profile?: any }) => {
  const { data } = await apiClient.post('/generate-docs', payload);
  return data;
};

export const approveJob = async (id: string, payload: Partial<Job>) => {
  const { data } = await apiClient.post(`/jobs/${id}/approve`, payload);
  return data;
};

export const rejectJob = async (id: string) => {
  const { data } = await apiClient.post(`/jobs/${id}/reject`);
  return data;
};

export const deleteJob = async (id: string) => {
  const { data } = await apiClient.delete(`/jobs/${id}`);
  return data;
};

export const markJobDispatched = async (id: string) => {
  const { data } = await apiClient.post(`/jobs/${id}/mark-dispatched`);
  return data;
};

export const searchJobs = async (q: string) => {
  const { data } = await apiClient.get('/search', { params: { q, type: 'job' } });
  return data;
};

export interface EmailReply {
  id: string;
  record_id: string;
  from_email: string;
  from_name: string;
  subject: string;
  body_text: string;
  received_at: string;
  category: 'interview_invite' | 'rejection' | 'info_request' | 'offer' | 'acknowledgement' | 'unknown';
  ai_draft: string | null;
  is_read: number;
}

export const getJobReplies = async (jobId: string) => {
  const { data } = await apiClient.get(`/jobs/${jobId}/replies`);
  return data as EmailReply[];
};

export const markReplyRead = async (replyId: string) => {
  const { data } = await apiClient.post(`/replies/${replyId}/read`);
  return data;
};
