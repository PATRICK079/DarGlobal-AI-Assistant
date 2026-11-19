
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ChatPayload = {
  question?: unknown;
  history?: unknown;
  search_state?: unknown;
};

export async function POST(request: Request) {
  let payload: ChatPayload;

  // 1. Parse incoming request
  try {
    payload = await request.json();
  } catch {
    return Response.json(
      { detail: "Invalid request. Please enter a question." },
      { status: 400 }
    );
  }

  // 2. Validate question
  const question = payload?.question;

  if (
    typeof question !== "string" ||
    question.trim().length < 2 ||
    question.length > 1000
  ) {
    return Response.json(
      {
        detail: "Enter a question between 2 and 1,000 characters.",
      },
      { status: 400 }
    );
  }

  // 3. Validate conversation history
  const rawHistory = payload?.history ?? [];

  if (
    !Array.isArray(rawHistory) ||
    rawHistory.length > 20 ||
    !rawHistory.every(
      (message) =>
        message !== null &&
        typeof message === "object" &&
        (message.role === "user" ||
          message.role === "assistant") &&
        typeof message.content === "string" &&
        message.content.trim().length > 0 &&
        message.content.length <= 4000
    )
  ) {
    return Response.json(
      { detail: "Invalid conversation history." },
      { status: 400 }
    );
  }

  const history: ChatMessage[] = rawHistory.map(
    (message) => ({
      role: message.role,
      content: message.content.trim(),
    })
  );

  // 4. Forward question and history to FastAPI
  try {
    const origin =
      process.env.BACKEND_URL ??
      "http://127.0.0.1:8000";

    const response = await fetch(
      new URL("/chat", origin),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question.trim(),
          history,
          search_state: payload.search_state,
        }),
        cache: "no-store",
        signal: AbortSignal.timeout(90_000),
      }
    );

    // 5. Return FastAPI response to frontend
    const data = await response.json();

    return Response.json(data, {
      status: response.status,
    });
  } catch (error) {
    console.error("Chat API request failed:", error);

    return Response.json(
      {
        detail: "Chat is temporarily unavailable. Please try again.",
      },
      { status: 503 }
    );
  }
}
