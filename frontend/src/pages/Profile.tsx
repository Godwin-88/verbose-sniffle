import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProfile, updateProfile } from '@/api/profile';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from '@/components/ui/accordion';
import { Progress } from '@/components/ui/progress';
import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Save, Plus, Trash2, X } from 'lucide-react';

type ProfileData = Record<string, any>;

// ─── Tag input ───────────────────────────────────────────────────────────────
function TagInput({ values = [], onChange }: { values: string[]; onChange: (v: string[]) => void }) {
  const [input, setInput] = useState('');
  const add = () => {
    const val = input.trim();
    if (val && !values.includes(val)) onChange([...values, val]);
    setInput('');
  };
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); } }}
          placeholder="Type and press Enter…"
          className="text-sm"
        />
        <Button type="button" variant="outline" size="sm" onClick={add}>Add</Button>
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((v) => (
            <Badge key={v} variant="secondary" className="gap-1 pr-1">
              {v}
              <button
                type="button"
                onClick={() => onChange(values.filter(x => x !== v))}
                className="hover:text-destructive"
              >
                <X className="w-3 h-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Repeatable row factory ───────────────────────────────────────────────────
function RepeatableSection<T extends Record<string, any>>({
  items = [],
  onChange,
  emptyItem,
  renderItem,
  addLabel,
}: {
  items: T[];
  onChange: (v: T[]) => void;
  emptyItem: T;
  renderItem: (item: T, update: (patch: Partial<T>) => void, remove: () => void) => React.ReactNode;
  addLabel: string;
}) {
  return (
    <div className="space-y-4">
      {items.map((item, i) => (
        <div key={i} className="border rounded-lg p-4 space-y-3 relative">
          {renderItem(
            item,
            (patch) => {
              const next = [...items];
              next[i] = { ...next[i], ...patch };
              onChange(next);
            },
            () => onChange(items.filter((_, j) => j !== i))
          )}
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...items, { ...emptyItem }])}
      >
        <Plus className="w-4 h-4 mr-2" /> {addLabel}
      </Button>
    </div>
  );
}

// ─── Completeness ────────────────────────────────────────────────────────────
function useCompleteness(profile: ProfileData) {
  return useCallback(() => {
    const checks = [
      { label: 'Personal info (name, email)', met: !!(profile.name && profile.email) },
      { label: 'Phone & location', met: !!(profile.phone && profile.location) },
      { label: 'Target roles set', met: !!(profile.target_roles?.length) },
      { label: 'Professional summary (50+ words)', met: !!(profile.summary?.split(' ').length >= 50) },
      { label: 'Education listed', met: !!(profile.education?.length) },
      { label: 'Work experience listed', met: !!(profile.experience?.length) },
      { label: 'Technical skills added', met: !!(profile.skills?.technical?.length) },
      { label: 'Certifications added', met: !!(profile.certifications?.length) },
      { label: 'Referee contact added', met: !!(profile.referees?.length) },
    ];
    const score = Math.round((checks.filter(c => c.met).length / checks.length) * 100);
    return { score, checks };
  }, [profile]);
}

export default function Profile() {
  const qc = useQueryClient();
  const { data: profileData, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: getProfile,
  });

  const [profile, setProfile] = useState<ProfileData>({});

  useEffect(() => {
    if (profileData?.profile) setProfile(profileData.profile);
  }, [profileData]);

  const mutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['profile'] }); toast.success('Profile saved'); },
    onError: () => toast.error('Failed to save profile'),
  });

  const set = (field: string, value: any) =>
    setProfile(prev => ({ ...prev, [field]: value }));

  const setNested = (parent: string, field: string, value: any) =>
    setProfile(prev => ({ ...prev, [parent]: { ...(prev[parent] || {}), [field]: value } }));

  const getCompleteness = useCompleteness(profile);
  const { score, checks } = getCompleteness();

  if (isLoading) {
    return <div className="flex items-center justify-center h-40 text-muted-foreground">Loading profile…</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-16">
      {/* Left: form */}
      <div className="lg:col-span-2 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">My Profile</h1>
          <Button onClick={() => mutation.mutate(profile)} disabled={mutation.isPending} size="sm">
            <Save className="w-4 h-4 mr-2" />
            {mutation.isPending ? 'Saving…' : 'Save Profile'}
          </Button>
        </div>

        <Accordion type="multiple" defaultValue={['personal', 'preferences', 'summary']} className="space-y-3">

          {/* Personal info */}
          <AccordionItem value="personal" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Personal Info
            </AccordionTrigger>
            <AccordionContent className="space-y-4 pt-1 pb-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Full Name</Label>
                  <Input value={profile.name || ''} onChange={e => set('name', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Email</Label>
                  <Input type="email" value={profile.email || ''} onChange={e => set('email', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Phone</Label>
                  <Input value={profile.phone || ''} onChange={e => set('phone', e.target.value)} placeholder="+254 7XX XXX XXX" />
                </div>
                <div className="space-y-1.5">
                  <Label>Location</Label>
                  <Input value={profile.location || ''} onChange={e => set('location', e.target.value)} placeholder="Nairobi, Kenya" />
                </div>
                <div className="col-span-2 space-y-1.5">
                  <Label>LinkedIn URL</Label>
                  <Input value={profile.linkedin || ''} onChange={e => set('linkedin', e.target.value)} placeholder="linkedin.com/in/yourname" />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Target preferences */}
          <AccordionItem value="preferences" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Target Preferences
            </AccordionTrigger>
            <AccordionContent className="space-y-4 pt-1 pb-4">
              <div className="space-y-1.5">
                <Label>Target Roles</Label>
                <TagInput
                  values={profile.target_roles || []}
                  onChange={v => set('target_roles', v)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Target Sectors</Label>
                <TagInput
                  values={profile.target_sectors || []}
                  onChange={v => set('target_sectors', v)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Preferred Locations</Label>
                <TagInput
                  values={profile.locations_ok || []}
                  onChange={v => set('locations_ok', v)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Minimum Salary (KSh)</Label>
                <Input
                  type="number"
                  value={profile.min_salary_ksh || ''}
                  onChange={e => set('min_salary_ksh', Number(e.target.value))}
                  placeholder="120000"
                />
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Summary */}
          <AccordionItem value="summary" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Professional Summary
            </AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <Textarea
                rows={5}
                value={profile.summary || ''}
                onChange={e => set('summary', e.target.value)}
                placeholder="Results-driven professional with X years…"
                className="resize-none"
              />
              <p className="text-xs text-muted-foreground mt-1">
                {profile.summary?.split(/\s+/).filter(Boolean).length || 0} words (aim for 50+)
              </p>
            </AccordionContent>
          </AccordionItem>

          {/* Education */}
          <AccordionItem value="education" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Education
            </AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <RepeatableSection
                items={profile.education || []}
                onChange={v => set('education', v)}
                emptyItem={{ degree: '', institution: '', year: '', grade: '' }}
                addLabel="Add education"
                renderItem={(item, update, remove) => (
                  <>
                    <div className="flex justify-end">
                      <Button type="button" variant="ghost" size="icon" onClick={remove} className="h-7 w-7 text-muted-foreground hover:text-destructive">
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label>Degree</Label>
                        <Input value={item.degree} onChange={e => update({ degree: e.target.value })} placeholder="MSc Statistics" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Institution</Label>
                        <Input value={item.institution} onChange={e => update({ institution: e.target.value })} placeholder="University of Nairobi" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Year</Label>
                        <Input value={item.year} onChange={e => update({ year: e.target.value })} placeholder="2020" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Grade / Honours</Label>
                        <Input value={item.grade} onChange={e => update({ grade: e.target.value })} placeholder="Distinction" />
                      </div>
                    </div>
                  </>
                )}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Experience */}
          <AccordionItem value="experience" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Work Experience
            </AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <RepeatableSection<{ title: string; company: string; dates: string; bullets: string[] }>
                items={profile.experience || []}
                onChange={v => set('experience', v)}
                emptyItem={{ title: '', company: '', dates: '', bullets: [] as string[] }}
                addLabel="Add experience"
                renderItem={(item, update, remove) => (
                  <>
                    <div className="flex justify-end">
                      <Button type="button" variant="ghost" size="icon" onClick={remove} className="h-7 w-7 text-muted-foreground hover:text-destructive">
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label>Job Title</Label>
                        <Input value={item.title} onChange={e => update({ title: e.target.value })} placeholder="Senior Data Analyst" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Company</Label>
                        <Input value={item.company} onChange={e => update({ company: e.target.value })} placeholder="Kenya Revenue Authority" />
                      </div>
                      <div className="col-span-2 space-y-1.5">
                        <Label>Dates</Label>
                        <Input value={item.dates} onChange={e => update({ dates: e.target.value })} placeholder="2021 – Present" />
                      </div>
                      <div className="col-span-2 space-y-1.5">
                        <Label>Key Achievements (one per line)</Label>
                        <Textarea
                          rows={4}
                          className="resize-none text-sm"
                          value={Array.isArray(item.bullets) ? item.bullets.join('\n') : item.bullets || ''}
                          onChange={e => update({ bullets: e.target.value.split('\n') })}
                          placeholder="Built automated ETL pipeline reducing reporting from 3 days to 4 hours"
                        />
                      </div>
                    </div>
                  </>
                )}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Skills */}
          <AccordionItem value="skills" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">Skills</AccordionTrigger>
            <AccordionContent className="space-y-4 pt-1 pb-4">
              <div className="space-y-1.5">
                <Label>Technical Skills</Label>
                <TagInput
                  values={profile.skills?.technical || []}
                  onChange={v => setNested('skills', 'technical', v)}
                />
              </div>
              <Separator />
              <div className="space-y-1.5">
                <Label>Soft Skills</Label>
                <TagInput
                  values={profile.skills?.soft || []}
                  onChange={v => setNested('skills', 'soft', v)}
                />
              </div>
              <Separator />
              <div className="space-y-1.5">
                <Label>Languages</Label>
                <TagInput
                  values={profile.skills?.languages || []}
                  onChange={v => setNested('skills', 'languages', v)}
                />
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Certifications */}
          <AccordionItem value="certifications" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Certifications
            </AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <RepeatableSection<{ name: string }>
                items={(profile.certifications || []).map((c: any) =>
                  typeof c === 'string' ? { name: c } : c
                )}
                onChange={v => set('certifications', v.map((c) => c.name))}
                emptyItem={{ name: '' }}
                addLabel="Add certification"
                renderItem={(item, update, remove) => (
                  <div className="flex gap-2">
                    <Input
                      value={item.name}
                      onChange={e => update({ name: e.target.value })}
                      placeholder="Google Data Analytics Certificate (2022)"
                      className="flex-1"
                    />
                    <Button type="button" variant="ghost" size="icon" onClick={remove} className="shrink-0 text-muted-foreground hover:text-destructive">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                )}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Achievements */}
          <AccordionItem value="achievements" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">
              Notable Achievements
            </AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <RepeatableSection<{ text: string }>
                items={(profile.notable_achievements || []).map((a: any) =>
                  typeof a === 'string' ? { text: a } : a
                )}
                onChange={v => set('notable_achievements', v.map((a) => a.text))}
                emptyItem={{ text: '' }}
                addLabel="Add achievement"
                renderItem={(item, update, remove) => (
                  <div className="flex gap-2">
                    <Input
                      value={item.text}
                      onChange={e => update({ text: e.target.value })}
                      placeholder="KRA Director General Award for Innovation (2023)"
                      className="flex-1"
                    />
                    <Button type="button" variant="ghost" size="icon" onClick={remove} className="shrink-0 text-muted-foreground hover:text-destructive">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                )}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Referees */}
          <AccordionItem value="referees" className="border rounded-lg px-4 bg-card">
            <AccordionTrigger className="hover:no-underline text-sm font-semibold">Referees</AccordionTrigger>
            <AccordionContent className="pt-1 pb-4">
              <RepeatableSection
                items={profile.referees || []}
                onChange={v => set('referees', v)}
                emptyItem={{ name: '', title: '', email: '', phone: '' }}
                addLabel="Add referee"
                renderItem={(item, update, remove) => (
                  <>
                    <div className="flex justify-end">
                      <Button type="button" variant="ghost" size="icon" onClick={remove} className="h-7 w-7 text-muted-foreground hover:text-destructive">
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label>Name</Label>
                        <Input value={item.name} onChange={e => update({ name: e.target.value })} placeholder="Dr. Alice Mwangi" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Title / Role</Label>
                        <Input value={item.title} onChange={e => update({ title: e.target.value })} placeholder="Head of Research, KRA" />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Email</Label>
                        <Input type="email" value={item.email} onChange={e => update({ email: e.target.value })} />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Phone</Label>
                        <Input value={item.phone} onChange={e => update({ phone: e.target.value })} />
                      </div>
                    </div>
                  </>
                )}
              />
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        <Button className="w-full h-11" onClick={() => mutation.mutate(profile)} disabled={mutation.isPending}>
          <Save className="w-4 h-4 mr-2" />
          {mutation.isPending ? 'Saving…' : 'Save Profile'}
        </Button>
      </div>

      {/* Right: completeness + actions */}
      <div className="space-y-4 lg:sticky lg:top-4 self-start">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Profile Strength
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-1.5">
              <div className="flex justify-between text-sm">
                <span className="font-semibold">{score}%</span>
                <span className="text-muted-foreground">
                  {checks.filter(c => c.met).length}/{checks.length} complete
                </span>
              </div>
              <Progress value={score} className="h-2" />
            </div>
            <ul className="space-y-2 text-sm">
              {checks.map((item, i) => (
                <li key={i} className={`flex items-start gap-2 ${item.met ? 'text-green-600' : 'text-muted-foreground'}`}>
                  <span className={`mt-0.5 shrink-0 ${item.met ? 'text-green-500' : 'text-amber-500'}`}>
                    {item.met ? '✓' : '○'}
                  </span>
                  {item.label}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Account Info
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-2 text-muted-foreground">
            <div className="flex justify-between">
              <span>User ID</span>
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                {profileData?.user_id || '—'}
              </code>
            </div>
            <div className="flex justify-between">
              <span>Email</span>
              <span className="truncate max-w-[140px]">{profileData?.email || '—'}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
