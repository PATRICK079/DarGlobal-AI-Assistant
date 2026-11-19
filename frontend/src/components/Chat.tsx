"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { ask, type Reply } from "../lib/api";

type Exchange = { question: string; reply: Reply };
const CHAT_STORAGE_KEY = "darglobal-chat-v1";
const DAR_GLOBAL_RESULTS_URL = "https://data.fca.org.uk/artefacts/NSM/RNS/72dab3cd-9922-4b16-9e31-9f48b1d2a5d2.html";

const examples = [
  { label: "Explore DarGlobal developments", question: "Tell me about DarGlobal" },
  { label: "Search Wasalt listings", question: "What apartments are listed for sale in Riyadh?" },
];

const starterQuestions = [
  "Tell me about DarGlobal",
  "Show me apartments for sale in Riyadh",
  "Find commercial rentals in Jeddah",
];

export default function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Exchange[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [showHome, setShowHome] = useState(true);
  const [pending, setPending] = useState("");
  const [partialAnswer, setPartialAnswer] = useState("");
  const [error, setError] = useState("");
  const [showLatest, setShowLatest] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const conversation = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const questionInput = useRef<HTMLInputElement>(null);
  const activeRequest = useRef<AbortController | null>(null);

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
    const panel = dialog.current;
    if (!panel) return;
    if (showHome && panel.open) panel.close();
    if (!showHome && !panel.open) panel.showModal();
  }, [showHome]);

  useEffect(() => {
    if (!showHome && followLatest.current && (messages.length || pending || error)) {
      const panel = conversation.current;
      panel?.scrollTo({ top: panel.scrollHeight });
    }
  }, [messages, pending, partialAnswer, error, showHome]);

  function trackScroll(panel: HTMLDivElement) {
    const nearBottom = panel.scrollHeight - panel.clientHeight - panel.scrollTop <= 48;
    followLatest.current = nearBottom;
    setShowLatest(!nearBottom);
  }

  function jumpToLatest(focusPanel = true) {
    const panel = conversation.current;
    followLatest.current = true;
    setShowLatest(false);
    if (focusPanel) panel?.focus({ preventScroll: true });
    panel?.scrollTo({ top: panel.scrollHeight });
  }

  async function submit(value: string) {
    const question = value.trim();
    if (!historyLoaded || activeRequest.current || question.length < 2) return;
    const request = new AbortController();
    activeRequest.current = request;
    jumpToLatest(false);
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
      const reply = await ask(question, history, searchState, request.signal);
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        const words = reply.answer.match(/\S+\s*|\s+/g) ?? [];
        const batchSize = Math.max(1, Math.ceil(words.length / 70));
        let visible = "";
        for (let index = 0; index < words.length && !request.signal.aborted; index += batchSize) {
          visible += words.slice(index, index + batchSize).join("");
          setPartialAnswer(visible);
          await new Promise<void>((resolve) => setTimeout(resolve, 30));
        }
      }
      if (!request.signal.aborted) {
        setMessages((previous) => [...previous, { question, reply }]);
      }
    } catch (failure) {
      if (!request.signal.aborted) {
        setInput(question);
        setError(failure instanceof Error ? failure.message : "Chat is temporarily unavailable.");
      }
    } finally {
      if (activeRequest.current === request) {
        activeRequest.current = null;
        setPending("");
        setPartialAnswer("");
      }
    }
  }

  function clearChat() {
    followLatest.current = true;
    setShowLatest(false);
    activeRequest.current?.abort();
    activeRequest.current = null;
    setMessages([]);
    setInput("");
    setPending("");
    setPartialAnswer("");
    setError("");
    questionInput.current?.focus();
  }

  function openChat(question?: string) {
    followLatest.current = true;
    setShowLatest(false);
    if (question) setInput(question);
    setShowHome(false);
  }

  return (
    <>
      <section className="chat-landing" aria-labelledby="chat-welcome">
        <div className="welcome">
          <h2 id="chat-welcome">Your property search starts here.</h2>
          <p>Ask about DarGlobal developments or find Wasalt properties to buy or rent.</p>
          <p>This proof of concept covers Wasalt listings in Riyadh, Jeddah, Dammam, Al Khobar, and Makkah. It uses listings from the first page of each Wasalt catalogue.</p>
          <button className="start-chat" type="button" disabled={!historyLoaded} onClick={() => openChat()}>
            {messages.length || pending ? "Resume chat" : "Start chat"}
          </button>
          <div className="examples">
            {examples.map(({ label, question }) => (
              <button type="button" key={label} disabled={!historyLoaded} onClick={() => openChat(question)}>
                <span>{label}<small>{question}</small></span>
              </button>
            ))}
          </div>
        </div>
      </section>
      <dialog ref={dialog} className="chat-dialog" aria-label="DarGlobal property chat"
        onCancel={(event) => { event.preventDefault(); setShowHome(true); }}>
        <section className="chat">
          <header className="chat-navigation">
            <button type="button" aria-label="Back to home" onClick={() => setShowHome(true)}>
              <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m15 5-7 7 7 7" />
              </svg>
            </button>
            <div className="chat-brand">
              <Image src="/darglobal-logo.jpg" alt="DarGlobal" width={160} height={80} />
            </div>
          </header>
          <div className="conversation-panel">
            <div className="conversation" role="log" aria-live="polite" aria-label="Chat messages"
              ref={conversation} tabIndex={-1} onScroll={(event) => trackScroll(event.currentTarget)}>
              {messages.length === 0 && !pending && (
                <div className="chat-welcome">
                  <div className="chat-welcome-intro">
                    <h2>Welcome to your property assistant</h2>
                    <p>Explore DarGlobal developments and find properties to buy or rent on Wasalt.</p>
                  </div>
                  <div className="starter-questions" role="group" aria-label="Suggested questions">
                    {starterQuestions.map((question) => (
                      <button key={question} type="button" onClick={() => void submit(question)}>
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map(({ question, reply }, index) => (
                <article className="exchange" key={index}>
                  <p className="question">{question}</p>
                  <div className="assistant-row assistant-response">
                    <p className="answer">{reply.answer}</p>
                    {Boolean(reply.properties?.length) && (
                      <ol className="property-results" aria-label="Matching properties">
                        {reply.properties?.map((property) => (
                          <li key={property.id}>
                            <h3>{property.title}</h3>
                            <div className="property-details">
                              {property.price !== null && (
                                <p>
                                  <strong>Price:</strong> {property.currency} {property.price.toLocaleString("en-US")}
                                  {property.rental_period && ` ${property.rental_period}`}
                                </p>
                              )}
                              {property.location && <p><strong>Location:</strong> {property.location}</p>}
                              {property.bedrooms !== null && <p><strong>Bedrooms:</strong> {property.bedrooms}</p>}
                              {property.details?.area_sqm && (
                                <p>
                                  <strong>Area:</strong> {property.details.area_sqm.toLocaleString("en-US")} sqm {property.details.area_type}
                                </p>
                              )}
                              {Object.entries(property.details?.features ?? {}).map(([name, value]) => (
                                <p key={name}><strong>{name}:</strong> {value}</p>
                              ))}
                            </div>
                            <p className="property-view">
                              View it here:{" "}
                              <a href={property.url} target="_blank" rel="noreferrer">{property.title}</a>
                            </p>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                  {reply.has_more && index === messages.length - 1 && (
                    <button className="listing-link" type="button" disabled={Boolean(pending)} onClick={() => void submit("Next page")}>
                      Show more listings
                    </button>
                  )}
                  {reply.sources.filter(({ url }) => url !== DAR_GLOBAL_RESULTS_URL).map((listing) => (
                    <a className="listing-link" key={listing.id} href={listing.url} target="_blank" rel="noreferrer">
                      View {listing.title}
                    </a>
                  ))}
                </article>
              ))}
              {pending && (
                <div className="exchange">
                  <p className="question">{pending}</p>
                  {partialAnswer ? (
                    <div className="assistant-row" aria-hidden="true">
                      <p className="answer">{partialAnswer}</p>
                    </div>
                  ) : (
                    <div className="assistant-row typing-indicator" role="status">
                      <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span>
                      <span className="sr-only">Assistant is typing…</span>
                    </div>
                  )}
                </div>
              )}
              {error && <p className="error" role="alert">{error}</p>}
            </div>
            {showLatest && Boolean(messages.length || pending) && (
              <button type="button" className="latest-messages" onClick={() => jumpToLatest()}>
                <span aria-hidden="true">↓</span> Latest messages
              </button>
            )}
          </div>
          <form className="chat-controls" onSubmit={(event) => { event.preventDefault(); void submit(input); }}>
            <button className="clear-chat" type="button" onClick={clearChat}
              disabled={!historyLoaded || !(messages.length || pending || input || error)}>
              <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="m14 8 6.7-6.7 2 2L16 10a4 4 0 0 1 .4 4.5L9.5 7.6a4 4 0 0 1 4.5.4ZM8 9l7 7-2.8 6C7 20.9 3.1 17 2 11.8L8 9Z" />
              </svg>
              Clear chat
            </button>
            <label className="sr-only" htmlFor="question">Your property question</label>
            <div className="composer">
              <input ref={questionInput} id="question" value={input} maxLength={1000} onChange={(event) => setInput(event.target.value)}
                readOnly={Boolean(pending)} placeholder="Say hello or ask about a property" />
              <button type="submit" aria-label="Send message" title="Send message"
                disabled={!historyLoaded || Boolean(pending) || input.trim().length < 2}>
                <svg aria-hidden="true" width="21" height="21" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13" />
                </svg>
              </button>
            </div>
          </form>
        </section>
      </dialog>
    </>
  );
}
