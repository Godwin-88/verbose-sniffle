import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { setupProfile } from '@/api/profile';
import { useAuthStore } from '@/store/auth';
import { supabase, supabaseConfigured } from '@/lib/supabase';
import { toast } from 'sonner';
import { Mail, Lock, AlertTriangle, ArrowRight, Zap } from 'lucide-react';

type Mode = 'sign_in' | 'sign_up';

export default function Setup() {
  const [mode, setMode] = useState<Mode>('sign_in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const afterSupabaseLogin = async (_id: string, userEmail: string) => {
    const profile = await setupProfile({ email: userEmail });
    setAuth(profile.api_key, profile.user_id);
    toast.success(mode === 'sign_up' ? 'Account created — welcome!' : 'Signed in');
    navigate('/');
  };

  const handleEmailAuth = async () => {
    if (!email.trim() || !password) return;
    setLoading(true);
    try {
      if (mode === 'sign_up') {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        if (data.session) {
          await afterSupabaseLogin(data.user!.id, email);
        } else {
          toast.info('Check your email to confirm your account, then sign in.');
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        await afterSupabaseLogin(data.user.id, email);
      }
    } catch (err: any) {
      toast.error(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLink = async () => {
    if (!email.trim()) { toast.error('Enter your email first'); return; }
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });
      if (error) throw error;
      toast.success('Magic link sent — check your inbox');
    } catch (err: any) {
      toast.error(err.message || 'Failed to send magic link');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) toast.error(error.message);
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* ── Left panel — branding ── */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] shrink-0 bg-primary p-12 text-white">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-white/15 backdrop-blur-sm">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="font-semibold text-lg tracking-tight">Job Hunter KE</span>
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <h1 className="text-4xl font-bold leading-tight tracking-tight">
              Land your next role,<br />automatically.
            </h1>
            <p className="text-white/70 text-base leading-relaxed">
              AI-powered job and scholarship applications. We scrape, craft your cover letters, and send — you just approve.
            </p>
          </div>

          <div className="space-y-3">
            {[
              'Scrapes 10+ Kenyan job boards daily',
              'Tailored cover letters generated in seconds',
              'One-click approve and dispatch',
            ].map((f) => (
              <div key={f} className="flex items-center gap-3 text-sm text-white/80">
                <div className="w-1.5 h-1.5 rounded-full bg-white/60 shrink-0" />
                {f}
              </div>
            ))}
          </div>
        </div>

        <p className="text-white/40 text-xs">© 2026 Job Hunter KE. Built for Kenya.</p>
      </div>

      {/* ── Right panel — auth form ── */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-[400px] space-y-8">

          {/* Mobile logo */}
          <div className="flex lg:hidden items-center gap-2">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold">Job Hunter KE</span>
          </div>

          {/* Supabase warning */}
          {!supabaseConfigured && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-300">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                Add <code className="font-mono text-xs bg-amber-100 dark:bg-amber-900 px-1 rounded">VITE_SUPABASE_URL</code> and <code className="font-mono text-xs bg-amber-100 dark:bg-amber-900 px-1 rounded">VITE_SUPABASE_ANON_KEY</code> to your <code className="font-mono text-xs">.env</code> then restart.
              </span>
            </div>
          )}

          {/* Header */}
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              {mode === 'sign_in' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="text-sm text-muted-foreground">
              {mode === 'sign_in'
                ? 'Sign in to your dashboard'
                : 'Start automating your applications today'}
            </p>
          </div>

          <div className="space-y-4">
            {/* Google */}
            <button
              onClick={handleGoogle}
              disabled={loading || !supabaseConfigured}
              className="w-full flex items-center justify-center gap-3 rounded-lg border border-border bg-card hover:bg-muted/50 px-4 py-2.5 text-sm font-medium text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">or</span>
              </div>
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-medium">Email address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-9"
                  autoFocus
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder={mode === 'sign_up' ? 'Min. 8 characters' : '••••••••'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleEmailAuth()}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Primary CTA */}
            <Button
              className="w-full gap-2"
              onClick={handleEmailAuth}
              disabled={loading || !email.trim() || !password || !supabaseConfigured}
            >
              {loading
                ? (mode === 'sign_in' ? 'Signing in…' : 'Creating account…')
                : (mode === 'sign_in' ? 'Sign in' : 'Create account')}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </Button>

            {/* Magic link */}
            <button
              type="button"
              onClick={handleMagicLink}
              disabled={loading || !supabaseConfigured}
              className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
            >
              Send a magic link instead →
            </button>
          </div>

          {/* Toggle sign in / sign up */}
          <p className="text-center text-sm text-muted-foreground">
            {mode === 'sign_in' ? "Don't have an account? " : 'Already have an account? '}
            <button
              type="button"
              className="font-medium text-primary hover:underline underline-offset-4"
              onClick={() => setMode(mode === 'sign_in' ? 'sign_up' : 'sign_in')}
            >
              {mode === 'sign_in' ? 'Sign up free' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
