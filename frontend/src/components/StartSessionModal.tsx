import { useEffect, useState } from 'react';
import { BatteryCharging, QrCode, Target } from 'lucide-react';
import { Alert } from '../ui/Feedback';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';
import { MOCK_USER_LAT, MOCK_USER_LNG } from '../lib/geo';

interface StartSessionModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (initialPercentage: number, targetPercentage: number, qrCode: string, latitude: number, longitude: number) => void;
  isLoading?: boolean;
  portQrCode?: string;
}

export function StartSessionModal({ open, onClose, onConfirm, isLoading = false, portQrCode }: StartSessionModalProps) {
  const [initialPercentage, setInitialPercentage] = useState(20);
  const [targetPercentage, setTargetPercentage] = useState(80);
  const [qrCode, setQrCode] = useState('');

  useEffect(() => {
    if (open) {
      setInitialPercentage(20);
      setTargetPercentage(80);
      setQrCode(portQrCode ?? '');
    }
  }, [open, portQrCode]);

  const isValid = initialPercentage >= 0 && initialPercentage < 100 && targetPercentage > initialPercentage && targetPercentage <= 100 && qrCode.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Start charging"
      description="Enter your vehicle's current and target battery level, and scan the port's QR code to check in."
      size="sm"
      preventClose={isLoading}
      footer={<><Button onClick={onClose} disabled={isLoading}>Not now</Button><Button variant="primary" onClick={() => onConfirm(initialPercentage, targetPercentage, qrCode, MOCK_USER_LAT, MOCK_USER_LNG)} isLoading={isLoading} disabled={!isValid}>Start charging</Button></>}
    >
      <div className="flex flex-col gap-5">
        <Field label="Current battery level" hint="What the vehicle's dashboard shows right now.">
          {({ id, describedBy }) => (
            <div className="relative"><BatteryCharging size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" /><input id={id} aria-describedby={describedBy} className="field-control field-control-leading field-control-trailing" type="number" min={0} max={99} value={initialPercentage} onChange={(event) => setInitialPercentage(Number(event.target.value))} required /><span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm font-bold text-[var(--steel)]">%</span></div>
          )}
        </Field>
        <Field label="Target battery level" hint="Charging stops delivering energy once this is reached.">
          {({ id, describedBy }) => (
            <div className="relative"><Target size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" /><input id={id} aria-describedby={describedBy} className="field-control field-control-leading field-control-trailing" type="number" min={1} max={100} value={targetPercentage} onChange={(event) => setTargetPercentage(Number(event.target.value))} required /><span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm font-bold text-[var(--steel)]">%</span></div>
          )}
        </Field>
        <Field label="QR code" hint="Scan or enter the code shown on the physical charger.">
          {({ id, describedBy }) => (
            <div className="relative"><QrCode size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" /><input id={id} aria-describedby={describedBy} className="field-control field-control-leading" type="text" placeholder="e.g. PORT-A1-XXXX or scan" value={qrCode} onChange={(event) => setQrCode(event.target.value)} required /></div>
          )}
        </Field>

        {!isValid && (
          <Alert tone="warning" title="Check your inputs">
            The target level must be higher than the current level, both must be between 0 and 100%, and a QR code is required.
          </Alert>
        )}

        <p className="text-sm leading-6 text-[var(--steel-dark)]">
          Charging speed slows automatically above 80% to protect the battery. An energy pre-authorization hold is placed on your wallet based on the target you choose. Your GPS location is verified to be within 200m of the station.
        </p>
      </div>
    </Dialog>
  );
}
