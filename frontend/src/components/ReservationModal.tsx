import React from 'react';

interface ReservationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  stationName: string;
  portId: string;
  pricePerKwh: number;
  isLoading?: boolean;
}

export type { ReservationModalProps };

export const ReservationModal: React.FC<ReservationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  stationName,
  portId,
  pricePerKwh,
  isLoading = false
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 animate-fade-in-up">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Confirm Reservation</h2>
        
        <div className="space-y-4 mb-6 text-gray-600">
          <p>You are about to reserve a port at <strong>{stationName}</strong>.</p>
          
          <div className="bg-gray-50 p-4 rounded-lg text-sm border border-gray-100">
            <ul className="list-disc list-inside space-y-2">
              <li><strong>Port ID:</strong> {portId.substring(0, 8)}...</li>
              <li><strong>Tariff:</strong> ₹{pricePerKwh}/kWh</li>
              <li>An escrow of <strong>₹1,000</strong> will be temporarily held from your wallet.</li>
              <li>You have <strong>15 minutes</strong> to arrive and plug in, otherwise the reservation will expire and the escrow will be forfeited as a penalty.</li>
            </ul>
          </div>
        </div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-medium disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Reserving...
              </>
            ) : 'Confirm & Reserve'}
          </button>
        </div>
      </div>
    </div>
  );
};
