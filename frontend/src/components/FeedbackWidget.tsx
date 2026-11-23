import { useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api";

const KINDS: [string, string][] = [
  ["unclear", "Not clear"], ["confusing", "Confusing"], ["bug", "Something broke"], ["idea", "Idea"], ["liked", "Liked it"],
];

/** Pilot feedback: a small button on every page. Notes are tied to the page the learner is on. */
export function FeedbackWidget() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("unclear");
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const send = async () => {
    setState("sending");
    try {
      await api("POST", "/api/feedback", { page: pathname, kind, rating: rating || null, message });
      setState("sent"); setMessage(""); setRating(0);
    } catch { setState("error"); }
  };
  const close = () => { setOpen(false); setState("idle"); };

  return (
    <div className="fb">
      {open && (
        <div className="fb-panel" role="dialog" aria-label="Send feedback">
          {state === "sent" ? (
            <>
              <p><b>Thank you!</b> That helps make this page better.</p>
              <button className="btn sm" onClick={close}>Close</button>
            </>
          ) : (
            <>
              <p className="fb-title">What happened on this page?</p>
              <div className="fb-kinds">
                {KINDS.map(([k, label]) => (
                  <button key={k} className={"btn sm" + (kind === k ? " pri" : "")} aria-pressed={kind === k} onClick={() => setKind(k)}>{label}</button>
                ))}
              </div>
              <textarea value={message} maxLength={1000} placeholder="Tell us in a sentence or two (optional)" aria-label="Your note" onChange={e => setMessage(e.target.value)} />
              <div className="fb-rate" role="group" aria-label="Rate this page">
                {[1, 2, 3, 4, 5].map(n => (
                  <button key={n} className={"btn sm" + (rating === n ? " pri" : "")} aria-pressed={rating === n} aria-label={n + " out of 5"} onClick={() => setRating(rating === n ? 0 : n)}>{n}</button>
                ))}
              </div>
              {state === "error" && <p className="fb-err">Could not send. Please try again in a moment.</p>}
              <div className="fb-actions">
                <button className="btn sm pri" disabled={state === "sending"} onClick={send}>{state === "sending" ? "Sending..." : "Send"}</button>
                <button className="btn sm" onClick={close}>Cancel</button>
              </div>
            </>
          )}
        </div>
      )}
      {!open && <button className="btn sm fb-open" onClick={() => setOpen(true)}>Feedback</button>}
    </div>
  );
}
