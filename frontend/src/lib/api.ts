export type Source = { id: number; title: string; url: string; source: string };
export type Property = {
  id: string;
  url: string;
  source: string;
  title: string;
  image_url: string | null;
  images?: string[];
  location: string | null;
  price: number | null;
  rental_period?: "monthly" | "yearly" | null;
  details?: {
    area_sqm?: number;
    area_type?: string;
    features?: Record<string, string>;
  } | null;
  currency: string;
  bedrooms: number | null;
};
type SearchState = { location: string | null; locations?: string[]; intended_use?: "residential" | "commercial" | null; page?: number; listing_id?: string | null; any_city?: boolean; showing_villa_alternatives?: boolean; awaiting?: "category" | "transaction_type" | "rental_period" | "location" | "search_adjustment" | null; filters: Record<string, string | boolean | number | null> };
export type Reply = { answer: string; sources: Source[]; properties?: Property[]; search_state?: SearchState; has_more?: boolean };

type ChatMessage = { role: "user" | "assistant"; content: string };

export async function ask(
  question: string, history: ChatMessage[] = [], searchState?: SearchState, signal?: AbortSignal,
): Promise<Reply> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history, search_state: searchState }),
    signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Chat is temporarily unavailable.");
  return data;
}
