import json
import uvicorn
import argparse
from fastapi import FastAPI, Response, Request


async def get_response_from_cache() -> dict | None:
    pass

async def save_response_to_cache() -> None:
    pass

async def clear_cache() -> None:
    pass

app = FastAPI()

@app.get("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request) -> Response:
    pass

def main():
    parser = argparse.ArgumentParser(description="Caching Proxy Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the proxy server on")
    parser.add_arguemnt("--origin", type=str, help="Origin server URL")
    parser.add_argument("--clear-cache", action="store_true", help="Clear all responses from cache")
    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()
        return
    
    if not args.origin:
        parser.error("Field not included: --origin")

    app.state.origin = args.origin

    uvicorn.run(app, host="127.0.0.1", port=args.port, reload=False)


if __name__ == "__main__":
    main()
