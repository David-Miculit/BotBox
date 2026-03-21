import signal
import sys
import argparse
from typing import Any
import requests
from groq import Groq
from config.settings import settings

groq_client = Groq(api_key=settings.groq_api_key)

API_BASE = settings.api_base_url
GROQ_MODEL = "llama-3.1-8b-instant"
TOP_K = 6
CHUNKS_PER_FILE = 2
CONTEXT_THRESHOLD = 10
REQUEST_TIMEOUT_SECONDS = 20
EXIT_COMMANDS = {"/exit", "exit", "quit", ":q"}

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are a helpful personal assistant for the user's uploaded files. "
        "Answer using the provided document context. "
        "If the answer is not in the document context, say that you could not find it "
        "in the uploaded files."
    ),
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agents_cli",
        description="CLI chatbot over your uploaded files",
    )
    parser.add_argument("--token", type=str, required=True)
    return parser.parse_args()

def retrieve_chunks(query: str, token: str, limit: int = TOP_K * CHUNKS_PER_FILE) -> list[dict[str, Any]]:
    try:
        res = requests.get(
            f"{API_BASE}/files/semantic_search",
            params={"q": query, "limit": limit},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"\n[warning] Failed to contact search API: {exc}")
        return []

    if not res.ok:
        body = res.text.strip()
        print(
            f"\n[warning] Search API returned {res.status_code}. "
            f"Response: {body[:300] if body else '<empty>'}"
        )
        return []

    try:
        payload = res.json()
    except ValueError:
        print("\n[warning] Search API returned non-JSON content.")
        return []

    return payload.get("results", [])

def can_answer_from_history(query: str, history: list[dict[str, str]]) -> bool:
    if not history:
        return False

    history_text = "\n".join(
        f"{m['role']}: {m['content'][:300]}" for m in history[-6:]
    )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Given the conversation history, can the user's new question be fully "
                    "answered from existing context? If not then search for it. "
                ),
            },
            {
                "role": "user",
                "content": f"History:\n{history_text}\n\nNew question: {query}",
            },
        ],
        max_tokens=5,
    )

    content = (response.choices[0].message.content or "").strip().lower()
    return content.startswith("yes")

def ask(query: str, token: str, history: list[dict[str, str]]) -> str:
    if can_answer_from_history(query, history):
        history.append({"role": "user", "content": query})

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[SYSTEM_PROMPT] + history,
            temperature=0.2,
        )

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "I could not generate an answer from the conversation history."

        history.append({"role": "assistant", "content": answer})
        return answer

    search_query = query.strip()
    chunks = retrieve_chunks(search_query, token)

    if not chunks:
        answer = "No relevant documents found."
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})
        return answer

    context = "\n\n".join(
        f"[{c.get('filename', 'unknown')}] {(c.get('chunk') or c.get('text') or '').strip()}"
        for c in chunks
        if (c.get("chunk") or c.get("text") or "").strip()
    )

    history.append(
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    )

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[SYSTEM_PROMPT] + history,
        temperature=0.2,
    )

    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        answer = "I could not generate an answer from the retrieved document context."

    history.append({"role": "assistant", "content": answer})
    return answer

def check_server():
    try:
        requests.get(f"{API_BASE}/healthz", timeout=3)
    except requests.ConnectionError:
        print(f"  server not reachable at {API_BASE}")
        sys.exit(1)

def goodbye() -> None:
    print("\n\nGoodbye! :)")
    sys.exit(0)

def main() -> None:
    if not settings.groq_api_key:
        raise ValueError("Missing groq_api_key in environment or .env.")
    if not settings.voyage_api_key:
        raise ValueError("Missing voyage_api_key in environment or .env.")

    check_server()
    args = parse_args()

    signal.signal(signal.SIGTERM, lambda *_: goodbye())
    print("\nWelcome")

    history: list[dict[str, str]] = []

    try:
        while True:
            query = input("> ").strip()

            if query.lower() in EXIT_COMMANDS:
                goodbye()

            if query.lower() == "/clear":
                history.clear()
                print("  context cleared.\n")
                continue

            if not query:
                continue

            if len(history) >= CONTEXT_THRESHOLD * 2:
                history.clear()
                print("  context limit reached, starting fresh.\n")

            answer = ask(query, args.token, history)
            print(f"\nbotbox: {answer}\n")

    except KeyboardInterrupt:
        goodbye()

if __name__ == "__main__":
    main()