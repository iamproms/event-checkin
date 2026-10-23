import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button } from './Button';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}

export function Dialog({ open, onClose, title, description, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);

  return <dialog
    ref={ref}
    className="ui-dialog"
    aria-labelledby={titleId}
    aria-describedby={description ? descriptionId : undefined}
    onCancel={(event) => { event.preventDefault(); onClose(); }}
  >
    <div className="ui-dialog__head">
      <h2 id={titleId}>{title}</h2>
      <Button variant="tertiary" onClick={onClose} aria-label="Close dialog">Close</Button>
    </div>
    {description && <p id={descriptionId} className="ui-dialog__description">{description}</p>}
    <div className="ui-dialog__body">{children}</div>
  </dialog>;
}
