import json
import uvicorn
import argparse
import httpx
from fastapi import FastAPI, Response, Request
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=60.0, follow_redirects=True) as client:
        app.state.client = client
        yield

async def get_response_from_cache() -> dict | None:
    pass

async def save_response_to_cache() -> None:
    pass

async def clear_cache() -> None:
    pass

app = FastAPI(lifespan=lifespan)

@app.get("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request) -> Response:
    origin_str = request.app.state.origin
    query_str = request.url.query

    target_url = f"{origin_str.rstrip('/')}/{path.lstrip('/')}"

    if query_str:
        target_url += f"?{query_str}"

    cache_key = f"{request.method}:{target_url}"

    if request.method == "GET":
        # Get cached reponse from Redis cache and return Response with cache HIT
        pass

    forward_headers = dict(request.headers)
    forward_headers.pop("accept-encoding", None)
    forward_headers.pop("content-length", None)
    forward_headers.pop("host", None)
    forward_headers["X-forwarded-for"] = request.client.host
    forward_headers["X-forwarded-proto"] = request.url.scheme

    client: httpx.AsyncClient = request.app.state.client
    body = await request.body()
    origin_response = await client.request(
        method=request.method,
        url=target_url,
        content=body,
        headers=forward_headers
    )

    response_headers = dict(origin_response.headers)
    response_headers.pop("content-encoding", None)
    response_headers.pop("content-length", None)
    response_headers.pop("transfer-encoding", None)

    if request.method == "GET" and origin_response.status_code == 200:
        # Save response to Redis cache using cache key
        # Return Response with cache MISS
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
