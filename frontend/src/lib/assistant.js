// Pure helpers for the Assistant page.
//
// The agent service holds no conversation state — it rebuilds the
// household's books from scratch on every call — so follow-up questions
// ("and the month before?") only work because the client replays what
// was said earlier. That replay is the logic worth keeping out of the
// component and testable on its own.

// Matches MAX_HISTORY_TURNS in both the backend and the agent. All three
// trim: this one keeps the request small, the others keep the prompt small.
export const MAX_HISTORY_TURNS = 6;

/** The text of an assistant turn, for replay as conversation history. */
export function answerText(result) {
  if (!result) return '';
  return result.answer || result.summary || result.headline || '';
}

/**
 * Pair each question with the answer it actually got.
 *
 * A turn that errored, or one still in flight, has no answer and is left
 * out — replaying "you were asked X" with nothing after it invites the
 * model to answer X a second time.
 */
export function buildHistory(turns) {
  const pairs = [];
  for (let i = 0; i < turns.length - 1; i += 1) {
    const q = turns[i];
    const a = turns[i + 1];
    if (q.role === 'user' && a.role === 'assistant' && answerText(a.result)) {
      pairs.push({ question: q.text, answer: answerText(a.result) });
    }
  }
  return pairs.slice(-MAX_HISTORY_TURNS);
}
