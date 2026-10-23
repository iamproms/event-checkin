import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../style.css';
import './examples.css';
import { Button, Dialog, Field, NavItem, Progress, Status, initializeTheme, setTheme, type Theme } from './index';

function Examples() {
  const [theme, updateTheme] = useState<Theme>(initializeTheme);
  const [compact, setCompact] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('Ọláwálé Adébáyọ̀');

  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    updateTheme(next);
  }

  return <main className="examples" data-density={compact ? 'compact' : 'comfortable'}>
    <header className="examples__header"><h1>UI primitives</h1><div className="examples__settings"><Button variant="secondary" onClick={toggleTheme}>Use {theme === 'light' ? 'dark' : 'light'} mode</Button><Button variant="secondary" onClick={() => setCompact(!compact)}>Use {compact ? 'comfortable' : 'compact'} density</Button></div></header>
    <section aria-labelledby="type-heading"><h2 id="type-heading">Typography and content</h2><p className="examples__body">Ọláwálé Adébáyọ̀ · Chidinma Nwankwọ · ₦12,450.00 · coordinator-for-lagos-main-entrance@example.org</p><p className="examples__support">Exported attendee details expire 90 days after the event ends. Anonymous attendance totals remain available.</p></section>
    <section aria-labelledby="buttons-heading"><h2 id="buttons-heading">Buttons</h2><div className="examples__row"><Button>Continue</Button><Button variant="secondary">Review details</Button><Button variant="tertiary">View policy</Button><Button variant="destructive">Delete record</Button><Button touchCritical>Gate action</Button><Button disabled>Unavailable</Button><Button loading loadingText="Saving changes…">Save changes</Button></div></section>
    <section aria-labelledby="fields-heading"><h2 id="fields-heading">Fields</h2><div className="examples__fields"><Field label="Coordinator name" value={name} onChange={(event) => setName(event.target.value)} hint="Use the name shown on staff records." /><Field label="Contact email" type="email" value="invalid-address" readOnly error="Enter a valid email address to continue." /></div></section>
    <section aria-labelledby="status-heading"><h2 id="status-heading">Status</h2><div className="examples__grid"><Status tone="success" title="Entry confirmed" instruction="Admit the ticket holder." /><Status tone="warning" title="Already checked in" instruction="Do not admit a second time; seek a supervisor if needed." /><Status tone="danger" title="Ticket not valid" instruction="Do not admit; seek a supervisor." /><Status tone="info" title="Verifying" instruction="Wait for server confirmation." /></div></section>
    <section aria-labelledby="nav-heading"><h2 id="nav-heading">Navigation</h2><nav aria-label="Specimen navigation" className="examples__nav"><NavItem href="#nav-heading" current>Overview</NavItem><NavItem href="#nav-heading">Participants</NavItem><NavItem href="#nav-heading">Reports</NavItem></nav></section>
    <section aria-labelledby="progress-heading"><h2 id="progress-heading">Progress and dialog</h2><div className="examples__fields"><Progress label="Import preview" value={45} /><Progress label="Preparing report" /></div><Button variant="secondary" onClick={() => setDialogOpen(true)}>Open dialog</Button><Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Confirm action" description="Review the scope before continuing."><p>No changes have been submitted.</p><Button onClick={() => setDialogOpen(false)}>Continue</Button></Dialog></section>
  </main>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing root element');
createRoot(root).render(<Examples />);
