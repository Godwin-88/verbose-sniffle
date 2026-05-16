import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { useAuthStore } from '@/store/auth';
import { setupProfile, getProfile } from '@/api/profile';
import { toast } from 'sonner';

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  useEffect(() => {
    const handleCallback = async () => {
      const { data, error } = await supabase.auth.getSession();
      if (error || !data.session) {
        toast.error('Authentication failed — please try again');
        navigate('/setup');
        return;
      }
      const user = data.session.user;
      try {
        const profile = await getProfile();
        setAuth(profile.api_key, profile.user_id);
      } catch {
        const profile = await setupProfile({ email: user.email || '' });
        setAuth(profile.api_key, profile.user_id);
      }
      toast.success('Signed in successfully');
      navigate('/');
    };
    handleCallback();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center text-muted-foreground">
      Signing you in…
    </div>
  );
}
