import { apiClient } from './client';

export interface Scholarship {
  id: string;
  title: string;
  funder?: string;
  company?: string;
  funder_country?: string;
  country?: string;
  level?: string;
  funding_type?: string;
  deadline: string;
  url: string;
  match_score?: number;
  status: 'pending' | 'ready_for_review' | 'approved' | 'dispatched' | 'rejected';
  motivation_letter?: string;
  research_proposal?: string;
  tailored_resume?: any;
  full_doc_md?: string;
  scraped_at: string;
  region?: string;
  source?: string;
  snippet?: string;
}

export const getScholarships = async (params: {
  status?: string;
  funding_type?: string;
  region?: string;
  level?: string;
  funder_country?: string;
  page?: number;
  per_page?: number;
}) => {
  const { data } = await apiClient.get('/scholarships', { params });
  return data;
};

export const getScholarship = async (id: string) => {
  const { data } = await apiClient.get(`/scholarships/${id}`);
  return data;
};

export const scrapeScholarships = async (payload: {
  keywords?: string[];
  sources?: string[];
  region_filter?: string;
  funding_filter?: string;
}) => {
  const { data } = await apiClient.post('/scholarships/scrape', payload);
  return data;
};

export const generateScholarshipDocs = async (payload: {
  scholarship_id?: string;
  max?: number;
  profile?: any;
}) => {
  const { data } = await apiClient.post('/scholarships/generate-docs', payload);
  return data;
};

export const approveScholarship = async (id: string, payload: Partial<Scholarship>) => {
  const { data } = await apiClient.post(`/scholarships/${id}/approve`, payload);
  return data;
};

export const rejectScholarship = async (id: string) => {
  const { data } = await apiClient.post(`/scholarships/${id}/reject`);
  return data;
};

export const deleteScholarship = async (id: string) => {
  const { data } = await apiClient.delete(`/scholarships/${id}`);
  return data;
};

export const markScholarshipDispatched = async (id: string) => {
  const { data } = await apiClient.post(`/scholarships/${id}/mark-dispatched`);
  return data;
};

export const searchScholarships = async (q: string) => {
  const { data } = await apiClient.get('/search', { params: { q, type: 'scholarship' } });
  return data;
};
