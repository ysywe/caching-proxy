import json
import uvicorn
import argparse
import httpx
import redis.asyncio
import asyncio
from fastapi import FastAPI, Response, Request
from contextlib import asynccontextmanager
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    redis_client = redis.asyncio.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )

    async with httpx.AsyncClient(limits=limits, timeout=60.0, follow_redirects=True) as client:
        app.state.client = client
        app.state.redis = redis_client
        yield

    await redis_client.close()

async def get_response_from_cache(redis_client, cache_key: str) -> dict | None:
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    return None

async def save_response_to_cache(cache_payload: dict, redis_client, cache_key: str) -> None:
    await redis_client.set(cache_key, json.dumps(cache_payload), ex=3600)

async def clear_cache() -> None:
    redis_client = redis.asyncio.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
    try:
        await redis_client.flushdb()
        print("Redis cache successfully cleared")
    except Exception as e:
        print(f"Failed to clear cache: {e}")
    finally:
        await redis_client.close()


app = FastAPI(lifespan=lifespan)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    origin_str = request.app.state.origin
    redis_client = request.app.state.redis
    query_str = request.url.query

    target_url = f"{origin_str.rstrip('/')}/{path.lstrip('/')}"

    if query_str:
        target_url += f"?{query_str}"

    cache_key = f"{request.method}:{target_url}"

    if request.method == "GET":
        cached_response = await get_response_from_cache(redis_client, cache_key)
        if cached_response:
            return Response(
                content=cached_response["content"].encode("utf-8"),
                status_code=cached_response["status_code"],
                headers={"X-Cache": "HIT", **cached_response["headers"]}
            )

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
        await save_response_to_cache(
            cache_payload={
                "content": origin_response.text,
                "status_code": origin_response.status_code,
                "headers": response_headers
            },
            redis_client=redis_client,
            cache_key=cache_key
        )

        return Response(
            content=origin_response.content,
            status_code=origin_response.status_code,
            headers={"X-Cache": "MISS", **response_headers}
        )
    return Response(
        content=origin_response.content,
        status_code=origin_response.status_code,
        headers={"X-Cache": "BYPASS", **response_headers}
    )

def main():
    parser = argparse.ArgumentParser(description="Caching Proxy Server")
    parser.add_argument("--port", type=int, default="0.0.0.0", help="Port to run the proxy server on")
    parser.add_argument("--origin", type=str, help="Origin server URL")
    parser.add_argument("--clear-cache", action="store_true", help="Clear all responses from cache")
    args = parser.parse_args()

    if args.clear_cache:
        asyncio.run(clear_cache())
        return
    
    if not args.origin:
        parser.error("Field not included: --origin")

    app.state.origin = args.origin

    uvicorn.run(app, host="0.0.0.0", port=args.port, reload=False)

if __name__ == "__main__":
    main()
