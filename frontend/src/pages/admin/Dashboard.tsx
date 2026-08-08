import React, { useState, useEffect } from 'react';
import { adminService } from '../../services/api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function AdminDashboard() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [assignData, setAssignData] = useState({ companyId: '', userId: '' });
  const navigate = useNavigate();
  const { logout } = useAuth();

  const loadCompanies = async () => {
    try {
      const data = await adminService.getCompanies();
      setCompanies(data);
    } catch (error) {
      console.error('Failed to load companies', error);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, []);

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompanyName.trim()) return;
    try {
      await adminService.createCompany({ name: newCompanyName });
      setNewCompanyName('');
      loadCompanies();
    } catch (error) {
      console.error('Failed to create company', error);
      alert('Error creating company');
    }
  };

  const handleAssignOperator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignData.companyId || !assignData.userId) return;
    try {
      await adminService.assignOperator(assignData.companyId, assignData.userId);
      setAssignData({ companyId: '', userId: '' });
      alert('Operator assigned successfully!');
    } catch (error) {
      console.error('Failed to assign operator', error);
      alert('Error assigning operator');
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-purple-600">Admin Dashboard</h1>
          <p className="text-skeuo-text-muted mt-2">Manage Companies and Operators</p>
        </div>
        <div className="flex gap-4">
          <button className="skeuo-btn" onClick={() => navigate('/driver/dashboard')}>
            Back to Main
          </button>
          <button className="skeuo-btn text-red-500 font-semibold" onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="skeuo-panel p-6 space-y-6">
          <h2 className="text-xl font-semibold">Create Company</h2>
          <form onSubmit={handleCreateCompany} className="space-y-4">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Company Name</label>
              <input
                type="text"
                className="skeuo-input"
                placeholder="Electra Corp..."
                value={newCompanyName}
                onChange={e => setNewCompanyName(e.target.value)}
              />
            </div>
            <button type="submit" className="skeuo-btn skeuo-btn-primary w-full">Create Company</button>
          </form>
        </div>

        <div className="skeuo-panel p-6 space-y-6">
          <h2 className="text-xl font-semibold">Assign Operator</h2>
          <form onSubmit={handleAssignOperator} className="space-y-4">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Company</label>
              <select 
                className="skeuo-input"
                value={assignData.companyId}
                onChange={e => setAssignData({...assignData, companyId: e.target.value})}
              >
                <option value="">Select Company...</option>
                {companies.map(c => (
                  <option key={c.company_id} value={c.company_id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">User ID (UUID)</label>
              <input
                type="text"
                className="skeuo-input"
                placeholder="Enter User ID..."
                value={assignData.userId}
                onChange={e => setAssignData({...assignData, userId: e.target.value})}
              />
            </div>
            <button type="submit" className="skeuo-btn skeuo-btn-primary w-full">Assign Operator</button>
          </form>
        </div>
      </div>

      <div className="skeuo-panel p-6 space-y-4">
        <h2 className="text-xl font-semibold">All Companies</h2>
        {companies.length === 0 ? (
          <p className="text-skeuo-text-muted text-center py-4">No companies found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/20 dark:border-white/5">
                  <th className="p-3">ID</th>
                  <th className="p-3">Name</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Created At</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <tr key={company.company_id} className="border-b border-white/10 dark:border-white/5 last:border-0 hover:bg-white/5 transition-colors">
                    <td className="p-3 text-xs font-mono text-skeuo-text-muted">{company.company_id}</td>
                    <td className="p-3 font-medium">{company.name}</td>
                    <td className="p-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${company.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                        {company.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="p-3 text-sm text-skeuo-text-muted">
                      {new Date(company.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
