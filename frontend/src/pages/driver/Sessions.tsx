import React from 'react';
import { Zap, Clock, Calendar } from 'lucide-react';

export const Sessions = () => {
  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-6">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-1">Charging Sessions</h1>
          <p className="text-skeuo-text-muted">View your active and past charging history.</p>
        </div>
      </header>

      <div className="skeuo-panel p-12 text-center opacity-80 border-dashed border-2 border-skeuo-text-muted/30">
        <div className="w-20 h-20 bg-skeuo-dark rounded-full shadow-skeuo-pressed flex items-center justify-center mb-6 mx-auto">
          <Zap size={40} className="text-skeuo-text-muted" />
        </div>
        <h2 className="text-2xl font-bold mb-2">No active sessions</h2>
        <p className="text-skeuo-text-muted max-w-md mx-auto">
          You don't have any ongoing charging sessions right now. Book a station to start charging.
        </p>
      </div>
      
      <div className="skeuo-panel p-6">
        <div className="flex items-center gap-2 mb-6">
          <Clock className="text-skeuo-text-muted" />
          <h3 className="text-lg font-bold">Session History</h3>
        </div>
        <div className="text-center py-8 text-skeuo-text-muted text-sm">
          No past sessions found.
        </div>
      </div>
    </div>
  );
};

export default Sessions;
