import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { authService } from '../../services/api';
import { Save, AlertTriangle, AlertCircle, CheckCircle2, User as UserIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Profile = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone_number: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        full_name: user.full_name,
        email: user.email,
        phone_number: user.phone_number || ''
      });
    }
  }, [user]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });
    setIsSubmitting(true);

    try {
      await authService.updateProfile({
        full_name: formData.full_name,
        phone_number: formData.phone_number
      });
      setMessage({ type: 'success', text: 'Profile updated successfully.' });
      // To strictly follow instructions: update state globally by forcing a reload 
      // or dispatching an event if fetchUser was globally available. 
      // Since context doesn't expose fetchUser directly, we will just reload the page to sync state.
      setTimeout(() => window.location.reload(), 1000);
    } catch (err: any) {
      console.error(err);
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to update profile.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      await authService.deleteAccount();
      logout();
      navigate('/login');
    } catch (err: any) {
      console.error(err);
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to delete account.' });
      setShowDeleteConfirm(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-6 h-full">
      <header className="flex justify-between items-end skeuo-panel p-6 shadow-sm border border-white/40">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <div className="p-2 bg-skeuo-dark rounded-xl shadow-skeuo-pressed">
              <UserIcon size={24} className="text-skeuo-accent" />
            </div>
            My Profile
          </h1>
          <p className="text-skeuo-text-muted mt-2">Manage your personal information and account settings.</p>
        </div>
      </header>

      {message.text && (
        <div className={`p-4 rounded-xl border flex items-center gap-2 font-medium ${message.type === 'error' ? 'bg-red-50 text-red-600 border-red-200' : 'bg-emerald-50 text-emerald-600 border-emerald-200'}`}>
          {message.type === 'error' ? <AlertCircle size={20} /> : <CheckCircle2 size={20} />}
          {message.text}
        </div>
      )}

      <div className="skeuo-panel p-6">
        <h2 className="text-xl font-bold mb-4 border-b border-white/10 pb-4">Personal Information</h2>
        
        <form onSubmit={handleUpdate} className="flex flex-col gap-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Full Name</label>
              <input
                type="text"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                required
                className="skeuo-input"
              />
            </div>
            
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Phone Number</label>
              <input
                type="text"
                name="phone_number"
                value={formData.phone_number}
                onChange={handleChange}
                className="skeuo-input"
                placeholder="+91..."
              />
            </div>
          </div>
          
          <div className="skeuo-text-field-group">
            <label className="skeuo-label">Email Address</label>
            <input
              type="email"
              value={formData.email}
              disabled
              className="skeuo-input opacity-70 cursor-not-allowed"
              title="Email cannot be changed"
            />
            <p className="text-xs text-skeuo-text-muted px-1">Your email address is used for login and cannot be changed.</p>
          </div>

          <div className="flex justify-end mt-4 pt-4 border-t border-white/10">
            <button 
              type="submit" 
              className="skeuo-btn skeuo-btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Save size={18} />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      <div className="skeuo-panel p-6 border-red-500/30">
        <h2 className="text-xl font-bold mb-4 text-red-500 flex items-center gap-2">
          <AlertTriangle size={24} />
          Danger Zone
        </h2>
        <p className="text-skeuo-text-muted mb-6">
          Permanently delete your account and all associated data. This action cannot be undone. Active charging sessions or reservations must be resolved before deletion.
        </p>
        
        {!showDeleteConfirm ? (
          <button 
            onClick={() => setShowDeleteConfirm(true)}
            className="skeuo-btn text-red-500 border-red-500/30 hover:bg-red-500/10 active:bg-red-500/20"
          >
            Delete Account
          </button>
        ) : (
          <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-xl">
            <p className="font-bold text-red-500 mb-4">Are you absolutely sure you want to delete your account?</p>
            <div className="flex gap-4">
              <button 
                onClick={handleDeleteAccount}
                className="skeuo-btn bg-red-500 text-white hover:bg-red-600 border-transparent shadow-[4px_4px_10px_rgba(239,68,68,0.3)] active:shadow-inner"
              >
                Yes, Delete My Account
              </button>
              <button 
                onClick={() => setShowDeleteConfirm(false)}
                className="skeuo-btn bg-skeuo-base"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Profile;
