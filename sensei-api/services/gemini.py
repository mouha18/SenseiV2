from google import genai
from google.genai.errors import ClientError


async def validate_key(plaintext: str) -> bool:
    client = genai.Client(api_key=plaintext)
    try:
        async for _ in await client.aio.models.list():
            break
    except ClientError:
        return False
    return True
