"use client";

import { useEffect, useRef, useState } from "react";
import { ask, type Reply } from "../lib/api";

type Exchange = { question: string; reply: Reply };
const CHAT_STORAGE_KEY = "darglobal-chat-v1";

const examples = [
  { source: "DarGlobal", question: "What types of homes does The Astera offer?" },
  { source: "Wasalt", question: "What apartments are listed for sale in Riyadh?" },
  { source: "DarGlobal", question: "Tell me about Trump Tower Jeddah." },
];

function AssistantIcon() {
  return (
    <span className="assistant-icon" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.5-3A7.5 7.5 0 1 1 20 11.5Z" />
        <path d="M9 11.5h.01m3.5 0h.01m3.5 0h.01" strokeWidth="2" />
      </svg>
    </span>
  );
}

export default function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Exchange[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [showHome, setShowHome] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(CHAT_STORAGE_KEY);
      if (saved) {
        const history: unknown = JSON.parse(saved);
        if (Array.isArray(history)) {
          setMessages(history.filter((entry) =>
            typeof entry?.question === "string"
            && typeof entry.reply?.answer === "string"
            && Array.isArray(entry.reply.sources)
            && (entry.reply.properties === undefined || Array.isArray(entry.reply.properties))
          ));
        }
      }
    } catch {
      // Chat remains available when browser storage cannot be read.
    } finally {
      setHistoryLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!historyLoaded) return;
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // Keep the current conversation available if browser storage is full or disabled.
    }
  }, [historyLoaded, messages]);

  useEffect(() => {
    if (!showHome && (messages.length || pending || error)) {
      end.current?.scrollIntoView({ block: "nearest" });
    }
  }, [messages, pending, error, showHome]);

  async function submit(value: string) {
    const question = value.trim();
    if (!historyLoaded || pending || question.length < 2) return;
    setInput("");
    setPending(question);
    setError("");
    try {
      const history = messages.slice(-5).flatMap(({ question, reply }) => {
        const listings = reply.properties?.map((property, index) =>
          [`${index + 1}. ${property.title}`, property.location,
            property.price === null ? null : [property.currency, property.price, property.rental_period].filter(Boolean).join(" ")]
            .filter(Boolean).join(" · "),
        ) ?? [];
        return [
          { role: "user" as const, content: question },
          { role: "assistant" as const, content: [reply.answer, ...listings].join("\n").slice(0, 2000) },
        ];
      });
      const searchState = [...messages].reverse().find(({ reply }) => reply.search_state)?.reply.search_state;
      const [reply] = await Promise.all([
        ask(question, history, searchState),
        new Promise<void>((resolve) => setTimeout(resolve, 400)),
      ]);
      setMessages((previous) => [...previous, { question, reply }]);
    } catch (failure) {
      setInput(question);
      setError(failure instanceof Error ? failure.message : "Chat is temporarily unavailable.");
    } finally {
      setPending("");
    }
  }

  return (
    <section className="chat" aria-label="Property chat">
      <div className="chat-navigation">
        {!showHome && messages.length > 0 && (
          <button type="button" onClick={() => setShowHome(true)}>← Back to home</button>
        )}
      </div>
      <div className="conversation" role="log" aria-live="polite">
        {historyLoaded && (showHome || (messages.length === 0 && !pending)) && (
          <div className="welcome">
            <AssistantIcon />
            <h2>How can I assist you?</h2>
            <p>For this proof of concept, Wasalt listing search covers Riyadh, Jeddah, Dammam, Al Khobar, and Makkah.</p>
            <div className="examples">
              {showHome ? (
                <button type="button" onClick={() => setShowHome(false)}>
                  Resume chat <span aria-hidden="true">↗</span>
                </button>
              ) : examples.map(({ source, question }) => (
                <button type="button" key={question} onClick={() => void submit(question)}>
                  <span><small>{source}</small>{question}</span>
                  <span aria-hidden="true">↗</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {!showHome && messages.map(({ question, reply }, index) => (
          <article className="exchange" key={index}>
            <p className="question">{question}</p>
            <div className="assistant-row">
              <AssistantIcon />
              <p className="answer">{reply.answer}</p>
            </div>
            {Boolean(reply.properties?.length) && (
              <ul className="property-results" aria-label="Matching properties">
                {reply.properties?.map((property) => (
                  <li key={property.id}>
                    <a href={property.url} target="_blank" rel="noreferrer">
                      {(property.images ?? (property.image_url ? [property.image_url] : [])).map((url) => (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={url} src={url} alt="" width={500} height={280} loading="lazy"
                          onError={(event) => { event.currentTarget.hidden = true; }}
                        />
                      ))}
                      <div className="property-details">
                        <h3>{property.title}</h3>
                        {property.price !== null && (
                          <p className="property-price">
                            {property.currency} {property.price.toLocaleString("en-US")}
                            {property.rental_period && ` ${property.rental_period}`}
                          </p>
                        )}
                        {property.location && <p>{property.location}</p>}
                        {property.details?.area_sqm && (
                          <p>{property.details.area_sqm.toLocaleString("en-US")} sqm {property.details.area_type}</p>
                        )}
                        {Object.entries(property.details?.features ?? {}).map(([name, value]) => (
                          <p key={name}>{name} {value}</p>
                        ))}
                        {property.bedrooms !== null && <p>{property.bedrooms} {property.bedrooms === 1 ? "bedroom" : "bedrooms"}</p>}
                        <span>{property.source === "DarGlobal" ? "View development on DarGlobal" : `View on ${property.source}`} <span aria-hidden="true">↗</span></span>
                      </div>
                    </a>
                  </li>
                ))}
              </ul>
            )}
            {reply.has_more && index === messages.length - 1 && (
              <button className="listing-link" type="button" disabled={Boolean(pending)} onClick={() => void submit("Next page")}>
                Show more listings
              </button>
            )}
            {reply.sources.map((listing) => (
              <a className="listing-link" key={listing.id} href={listing.url} target="_blank" rel="noreferrer">
                View {listing.title} <span aria-hidden="true">↗</span>
              </a>
            ))}
          </article>
        ))}
        {!showHome && pending && (
          <div className="exchange">
            <p className="question">{pending}</p>
            <div className="assistant-row" role="status">
              <AssistantIcon />
              <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span>
              <span className="typing-label">Assistant is typing…</span>
            </div>
          </div>
        )}
        {!showHome && error && <p className="error" role="alert">{error}</p>}
        <div ref={end} />
      </div>
      {!showHome && <form onSubmit={(event) => { event.preventDefault(); void submit(input); }}>
        <label className="sr-only" htmlFor="question">Your property question</label>
        <div className="composer">
          <input id="question" value={input} maxLength={1000} onChange={(event) => setInput(event.target.value)}
            readOnly={Boolean(pending)} placeholder="Say hello or ask about a property" />
          <button type="submit" disabled={Boolean(pending) || input.trim().length < 2}>Send <span aria-hidden="true">↑</span></button>
        </div>
      </form>}
    </section>
  );
}
