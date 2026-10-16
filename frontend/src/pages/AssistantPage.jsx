import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Icon, PageHeader } from '../components/ui';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';
import { buildHistory } from '../lib/assistant';
import AssistantAnswer from '../components/assistant/AssistantAnswer';
import ThinkingIndicator from '../components/assistant/ThinkingIndicator';

// What the assistant is for, phrased as things worth asking. Shown on an
// empty thread: a blank chat box with a blinking cursor tells a person
// nothing about what this can actually answer.
const SUGGESTIONS = [
  'Where did most of our money go last month?',
  'Are we going to stay within budget this month?',
  'What bills are coming up in the next two weeks?',
  'Is anything unusual in our spending?',
  'How much can we safely spend per day for the rest of the month?',
  'Which loan should we pay off first?',
];

// The transcript survives a refresh and a tab switch, but not closing the
// tab. sessionStorage rather than localStorage on purpose: this is a
// household's money discussed in detail, often on a shared computer, and
// a transcript that outlives the session is a liability nobody asked for.
const STORAGE_PREFIX = 'lc_assistant_thread:';

// Turn ids only need to be unique within one mounted thread — they are
// React keys, not anything persisted.
let nextId = 1;
const newId = () => `t${nextId++}`;

export default function AssistantPage() {
  const { user, household } = useAuth();
  const storageKey = STORAGE_PREFIX + (household?.id ?? user?.id ?? 'me');

  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(null); // { question, startedAt }
  const abortRef = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  // Restore the thread for this household. A read that throws (private
  // mode, blocked storage) just starts an empty conversation.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      const saved = raw ? JSON.parse(raw) : [];
      if (Array.isArray(saved)) setTurns(saved);
    } catch {
      /* no transcript to restore */
    }
  }, [storageKey]);

  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(turns));
    } catch {
      /* the conversation still works, it just will not survive a refresh */
    }
  }, [turns, storageKey]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns, pending]);

  // Abandon an in-flight run if the page goes away.
  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(
    async (question) => {
      const text = (question || '').trim();
      if (!text || pending) return;

      const history = buildHistory(turns);
      setTurns((prev) => [...prev, { id: newId(), role: 'user', text }]);
      setDraft('');
      const startedAt = Date.now();
      setPending({ question: text, startedAt });

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await api.ai.ask(text, history, controller.signal);
        setTurns((prev) => [
          ...prev,
          { id: newId(), role: 'assistant', result: res.result || {}, meta: res.meta },
        ]);
      } catch (err) {
        // A cancel is the user's own doing — take the question back out
        // rather than leaving it in the thread with an error under it.
        if (err?.name === 'AbortError') {
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            return last?.role === 'user' && last.text === text ? prev.slice(0, -1) : prev;
          });
        } else {
          setTurns((prev) => [
            ...prev,
            { id: newId(), role: 'error', text: err?.message || 'The assistant could not answer.', question: text },
          ]);
        }
      } finally {
        abortRef.current = null;
        setPending(null);
        inputRef.current?.focus();
      }
    },
    [pending, turns]
  );

  function onKeyDown(e) {
    // Enter sends, Shift+Enter breaks the line — what a chat box does.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  }

  function clearThread() {
    abortRef.current?.abort();
    setTurns([]);
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      /* nothing was stored */
    }
  }

  const isEmpty = turns.length === 0 && !pending;
  const firstName = useMemo(
    () => (user?.displayName || '').trim().split(/\s+/)[0] || '',
    [user]
  );

  return (
    <div className="chat-page">
      <PageHeader
        title="Assistant"
        subtitle="Ask about your household's money. It reads your own books to answer."
      >
        {turns.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearThread}>Clear chat</Button>
        )}
      </PageHeader>

      <div className="chat-thread">
        {isEmpty && (
          <div className="chat-welcome">
            <div className="chat-welcome-mark"><Icon name="assistant" size={26} /></div>
            <h2>{firstName ? `Hello, ${firstName}.` : 'Hello.'}</h2>
            <p>
              I can look at your transactions, budgets, bills, investments and goals, and
              answer questions about them. I only know what is in this household's books —
              I cannot look anything up outside them.
            </p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chat-suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t) => {
          if (t.role === 'user') {
            return (
              <div className="chat-turn chat-turn-user" key={t.id}>
                <div className="chat-bubble chat-bubble-user">{t.text}</div>
              </div>
            );
          }
          if (t.role === 'error') {
            return (
              <div className="chat-turn" key={t.id}>
                <div className="chat-avatar" aria-hidden="true"><Icon name="assistant" size={16} /></div>
                <div className="chat-bubble chat-bubble-error">
                  <div>{t.text}</div>
                  {t.question && (
                    <Button variant="ghost" size="sm" onClick={() => send(t.question)}>
                      Try again
                    </Button>
                  )}
                </div>
              </div>
            );
          }
          return (
            <div className="chat-turn" key={t.id}>
              <div className="chat-avatar" aria-hidden="true"><Icon name="assistant" size={16} /></div>
              <div className="chat-bubble">
                <AssistantAnswer result={t.result} meta={t.meta} />
              </div>
            </div>
          );
        })}

        {pending && (
          <div className="chat-turn">
            <div className="chat-avatar" aria-hidden="true"><Icon name="assistant" size={16} /></div>
            <div className="chat-bubble">
              <ThinkingIndicator startedAt={pending.startedAt} />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="chat-composer">
        <div className="chat-composer-row">
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about your spending, budget, bills, goals…"
            rows={1}
            maxLength={1000}
            disabled={!!pending}
            aria-label="Ask the assistant"
          />
          {pending ? (
            <Button variant="ghost" onClick={() => abortRef.current?.abort()}>Stop</Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => send(draft)}
              disabled={!draft.trim()}
              aria-label="Send"
            >
              <Icon name="send" size={16} />
            </Button>
          )}
        </div>
        <div className="chat-note">
          Answers are worked out from your own records. General guidance about this
          household's money only — not investment advice, and never a recommendation to
          buy a particular fund, stock or policy.
        </div>
      </div>
    </div>
  );
}
