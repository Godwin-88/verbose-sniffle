/**
 * Renders the structured tailored_resume / tailored_resume (scholarship) JSON object
 * returned by the API. The object shape is:
 * {
 *   match_score: number
 *   summary: string
 *   highlighted_skills: string[]
 *   keywords: string[]
 *   bullet_rewrites: { [original]: rewritten }
 *   markdown: string           — full rendered section
 *   strengths?: string[]       — scholarship only
 *   gaps?: string[]            — scholarship only
 * }
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge } from '@/components/ui/badge';
import { MatchBar } from './MatchBar';

interface ResumeData {
  match_score?: number;
  summary?: string;
  highlighted_skills?: string[];
  keywords?: string[];
  bullet_rewrites?: Record<string, string>;
  markdown?: string;
  strengths?: string[];
  gaps?: string[];
}

interface Props {
  data: ResumeData | string | null | undefined;
  showStrengthsGaps?: boolean;
}

export function ResumeInsights({ data, showStrengthsGaps = false }: Props) {
  if (!data) {
    return <p className="text-sm text-muted-foreground">No resume insights generated yet.</p>;
  }

  // If the API returned a raw string (legacy / parse error fallback), just render as markdown
  if (typeof data === 'string') {
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data}</ReactMarkdown>
      </div>
    );
  }

  const {
    match_score,
    summary,
    highlighted_skills = [],
    keywords = [],
    bullet_rewrites = {},
    markdown,
    strengths = [],
    gaps = [],
  } = data;

  const hasRewrites = Object.keys(bullet_rewrites).length > 0;

  return (
    <div className="space-y-6">
      {match_score !== undefined && (
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-muted-foreground">Match Score</span>
          <MatchBar score={match_score} />
        </div>
      )}

      {summary && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Tailored Summary
          </h4>
          <p className="text-sm leading-relaxed">{summary}</p>
        </div>
      )}

      {highlighted_skills.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Key Skills
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {highlighted_skills.map((s) => (
              <Badge key={s} variant="secondary" className="text-xs">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {keywords.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            ATS Keywords
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((k) => (
              <Badge key={k} variant="outline" className="text-xs font-mono">
                {k}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {hasRewrites && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Bullet Rewrites
          </h4>
          <div className="border rounded-md overflow-hidden text-sm">
            <div className="grid grid-cols-2 bg-muted px-3 py-2 font-medium text-xs text-muted-foreground uppercase tracking-wider">
              <span>Original</span>
              <span>Rewritten</span>
            </div>
            {Object.entries(bullet_rewrites).map(([orig, rewritten], i) => (
              <div
                key={i}
                className="grid grid-cols-2 gap-4 px-3 py-2 border-t text-xs leading-relaxed"
              >
                <span className="text-muted-foreground line-through">{orig}</span>
                <span className="text-foreground font-medium">{rewritten}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {showStrengthsGaps && (
        <>
          {strengths.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Key Strengths
              </h4>
              <ul className="space-y-1">
                {strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-green-500 mt-0.5">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {gaps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Gaps to Address
              </h4>
              <ul className="space-y-1">
                {gaps.map((g, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-amber-500 mt-0.5">⚠</span>
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {markdown && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Full CV Section Preview
          </h4>
          <div className="prose prose-sm max-w-none border rounded-lg p-4 bg-muted/20">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
