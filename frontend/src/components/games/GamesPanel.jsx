import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api';
import { Button, Modal, Pill, Select } from '../ui';
import { useToast } from '../../context/ToastContext';

const fmtCoins = (n) => Math.round(Number(n) || 0).toLocaleString('en-IN');

const BUCKETS = [
  { id: 'need', label: 'Need' },
  { id: 'want', label: 'Want' },
  { id: 'invest', label: 'Invest' },
];

function ResultBanner({ result }) {
  if (!result) return null;
  return (
    <div className={'game-result' + (result.passed ? ' win' : ' miss')}>
      <div className="game-result-title">
        {result.passed ? `+${fmtCoins(result.coins)} coins` : 'Not this time'}
      </div>
      <div className="note">{result.message}</div>
    </div>
  );
}

export function QuizModal({ onClose, onSubmit }) {
  const toast = useToast();
  const [round, setRound] = useState(null);
  const [picks, setPicks] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    let live = true;
    api.rewards.quiz().then((r) => {
      if (!live) return;
      setRound(r);
      if (r.played) {
        setResult({
          passed: r.passed,
          coins: r.coinsAwarded,
          message: r.passed
            ? `Already won ${fmtCoins(r.coinsAwarded)} coins today`
            : 'Already attempted today — a new quiz lands tomorrow',
        });
      }
    }).catch((e) => toast(e.message));
    return () => { live = false; };
  }, [toast]);

  async function submit() {
    if (!round?.questions?.length) return;
    if (round.questions.some((q) => picks[q.id] === undefined)) {
      toast('Answer every question first');
      return;
    }
    setBusy(true);
    try {
      const r = await onSubmit(round.questions.map((q) => ({ id: q.id, choice: picks[q.id] })));
      setResult(r);
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Daily money quiz" onClose={onClose} wide>
      <p>Four out of five unlocks a random coin drop. One try a day.</p>
      {!round ? (
        <div className="note">Shuffling today’s questions…</div>
      ) : result ? (
        <ResultBanner result={result} />
      ) : (
        <ol className="quiz-list">
          {round.questions.map((q, i) => (
            <li key={q.id} className="quiz-item">
              <div className="quiz-prompt">
                <span className="note">{i + 1}.</span> {q.prompt}
              </div>
              <div className="quiz-options">
                {q.options.map((opt, idx) => (
                  <button
                    key={opt}
                    type="button"
                    className={'quiz-opt' + (picks[q.id] === idx ? ' picked' : '')}
                    onClick={() => setPicks((p) => ({ ...p, [q.id]: idx }))}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}
      <div className="modal-footer">
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {!result && round && !round.played && (
          <Button variant="primary" onClick={submit} disabled={busy}>
            {busy ? 'Checking…' : 'Submit quiz'}
          </Button>
        )}
      </div>
    </Modal>
  );
}

export function PuzzleModal({ onClose, onSubmit }) {
  const toast = useToast();
  const [round, setRound] = useState(null);
  const [choice, setChoice] = useState(null);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    let live = true;
    api.rewards.puzzle().then((r) => {
      if (!live) return;
      setRound(r);
      if (r.kind === 'sorter') {
        const start = {};
        r.items.forEach((it) => { start[it.id] = 'need'; });
        setAnswers(start);
      }
      if (r.played) {
        setResult({
          passed: r.passed,
          coins: r.coinsAwarded,
          message: r.passed
            ? `Already won ${fmtCoins(r.coinsAwarded)} coins today`
            : 'Already attempted today — a new puzzle lands tomorrow',
        });
      }
    }).catch((e) => toast(e.message));
    return () => { live = false; };
  }, [toast]);

  function cycleBucket(id) {
    setAnswers((prev) => {
      const cur = prev[id] || 'need';
      const i = BUCKETS.findIndex((b) => b.id === cur);
      return { ...prev, [id]: BUCKETS[(i + 1) % BUCKETS.length].id };
    });
  }

  async function submit() {
    if (!round) return;
    setBusy(true);
    try {
      const payload = { id: round.id, choice, answers };
      const r = await onSubmit(payload);
      setResult(r);
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={round?.title || 'Daily money puzzle'} onClose={onClose} wide>
      <p>{round?.prompt || 'Loading today’s puzzle…'}</p>
      {result ? (
        <ResultBanner result={result} />
      ) : !round ? null : round.kind === 'riddle' ? (
        <div className="quiz-options">
          {round.options.map((opt, idx) => (
            <button
              key={opt}
              type="button"
              className={'quiz-opt' + (choice === idx ? ' picked' : '')}
              onClick={() => setChoice(idx)}
            >
              {opt}
            </button>
          ))}
        </div>
      ) : round.kind === 'sorter' ? (
        <div className="sorter-grid">
          {round.items.map((it) => {
            const bucket = answers[it.id] || 'need';
            return (
              <button key={it.id} type="button" className={'sorter-card bucket-' + bucket} onClick={() => cycleBucket(it.id)}>
                <div className="sorter-label">{it.label}</div>
                <Pill>{BUCKETS.find((b) => b.id === bucket)?.label}</Pill>
                <div className="note">Tap to change</div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="match-list">
          {round.items.map((it) => (
            <label key={it.id} className="match-row">
              <span>{it.term}</span>
              <Select
                value={answers[it.id] || ''}
                onChange={(e) => setAnswers((a) => ({ ...a, [it.id]: e.target.value }))}
                placeholder="Match…"
                options={round.options}
              />
            </label>
          ))}
        </div>
      )}
      <div className="modal-footer">
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {!result && round && !round.played && (
          <Button
            variant="primary"
            onClick={submit}
            disabled={busy || (round.kind === 'riddle' && choice === null)}
          >
            {busy ? 'Checking…' : 'Submit puzzle'}
          </Button>
        )}
      </div>
    </Modal>
  );
}

export function SpinModal({ onClose, onSpin }) {
  const toast = useToast();
  const [round, setRound] = useState(null);
  const [rotation, setRotation] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    let live = true;
    api.rewards.wheel().then((r) => {
      if (!live) return;
      setRound(r);
      if (r.played) {
        setResult({
          passed: true,
          coins: r.coinsAwarded,
          message: `Already spun today — ${fmtCoins(r.coinsAwarded)} coins`,
        });
      }
    }).catch((e) => toast(e.message));
    return () => { live = false; };
  }, [toast]);

  const gradient = useMemo(() => {
    const slices = round?.slices || [];
    if (!slices.length) return undefined;
    const step = 100 / slices.length;
    const stops = slices.map((s, i) => `${s.color} ${i * step}% ${(i + 1) * step}%`);
    return `conic-gradient(from -90deg, ${stops.join(', ')})`;
  }, [round]);

  async function spin() {
    if (spinning || !round || round.played) return;
    setSpinning(true);
    try {
      const r = await onSpin();
      const n = round.slices.length;
      const slice = 360 / n;
      const target = 360 * 6 + (360 - (r.segmentIndex * slice + slice / 2));
      setRotation(target);
      window.setTimeout(() => setResult(r), 4200);
    } catch (e) {
      toast(e.message);
      setSpinning(false);
    }
  }

  return (
    <Modal title="Spin the wheel" onClose={onClose} wide>
      <p>One spin a day. The slice it lands on is the payout — 10 to 100 coins.</p>
      <div className="wheel-stage">
        <div className="wheel-pointer" aria-hidden="true">▼</div>
        <div
          className={'wheel' + (spinning ? ' spinning' : '')}
          style={{ background: gradient, transform: `rotate(${rotation}deg)` }}
        >
          {(round?.slices || []).map((s, i) => {
            const n = round.slices.length;
            const angle = (360 / n) * i + 360 / n / 2;
            return (
              <span
                key={s.label + i}
                className="wheel-label"
                style={{ transform: `rotate(${angle}deg) translateY(-108px)` }}
              >
                {s.label}
              </span>
            );
          })}
        </div>
      </div>
      {result && <ResultBanner result={result} />}
      <div className="modal-footer">
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {!result && (
          <Button variant="primary" onClick={spin} disabled={spinning || !round || round.played}>
            {spinning ? 'Spinning…' : 'Spin'}
          </Button>
        )}
      </div>
    </Modal>
  );
}

export function GameCard({ game, onPlay }) {
  const { title, description, icon, payoutMin, payoutMax, hint, played, passed, coinsAwarded } = game;
  return (
    <div className={'card card-pad challenge-card' + (passed ? ' won' : '')}>
      <div className="challenge-head">
        <div className="challenge-icon" aria-hidden="true">{icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="challenge-title">{title}</div>
          <div className="note">{hint}</div>
        </div>
        <span className="coin-badge">🪙 {fmtCoins(payoutMin)}–{fmtCoins(payoutMax)}</span>
      </div>
      <div className="note" style={{ marginTop: 10 }}>{description}</div>
      <div className="challenge-actions">
        <Button size="sm" variant={played ? 'ghost' : 'primary'} onClick={onPlay}>
          {played ? (passed ? `Won ${fmtCoins(coinsAwarded)} today` : 'See result') : 'Play'}
        </Button>
      </div>
    </div>
  );
}
